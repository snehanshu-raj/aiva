from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import asyncio
import json
import os
import base64
from datetime import datetime
from typing import Optional
from pathlib import Path
import logging
import warnings

warnings.filterwarnings("ignore", message=".*non-text parts.*")
warnings.filterwarnings("ignore", message=".*non-data parts.*")
from google import genai
from google.genai import types
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

app = FastAPI(title="Vision Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set")

CAPTURES_DIR = Path("captures")
CAPTURES_DIR.mkdir(exist_ok=True)
DEFAULT_EMAIL = os.getenv("DEFAULT_EMAIL", "snehanshu.usc@gmail.com")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "snehanshu.usc@gmail.com")

METADATA_FILE = CAPTURES_DIR / "metadata.json"

def load_metadata():
    """Load metadata from disk"""
    if METADATA_FILE.exists():
        try:
            with open(METADATA_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Could not load metadata: {e}")
            return {}
    return {}

def save_metadata(metadata):
    """Save metadata to disk"""
    try:
        with open(METADATA_FILE, "w") as f:
            json.dump(metadata, f, indent=2)
        print(f"Metadata saved to {METADATA_FILE}")
    except Exception as e:
        print(f"Could not save metadata: {e}")

captured_frames = load_metadata()
MAX_METADATA_ENTRIES = 100


class SessionState:
    """Holds session state for continuous monitoring"""
    def __init__(self):
        self.continuous_mode = False
        self.last_description = ""
        self.monitoring_context = None  
        self.last_notification_time = datetime.now()


class VisionAssistantTools:
    """Tools that can be called via voice commands"""
    def __init__(self, get_latest_frame_callback, session_captures, session_state):
        self.get_latest_frame = get_latest_frame_callback
        self.session_captures = session_captures
        self.session_state = session_state
        self.processing_lock = asyncio.Lock()
        
    async def send_email(self, recipient: Optional[str] = None, subject: str = "Vision Assistant Capture", body: str = "Here's the image you requested.", attach_frame_id: Optional[str] = None):
        """Send email with optional image attachment using Gmail API"""
        
        if not recipient or recipient.lower() in ["me", "myself", "my email"]:
            recipient = DEFAULT_EMAIL
        
        SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
        
        def create_message_with_attachment(sender, to, subject, body_text, image_path=None):
            """Create email message with optional image attachment"""
            message = MIMEMultipart()
            message["to"] = to
            message["from"] = sender
            message["subject"] = subject
            
            msg = MIMEText(body_text)
            message.attach(msg)
            
            if image_path and Path(image_path).exists():
                with open(image_path, 'rb') as f:
                    img_data = f.read()
                image = MIMEImage(img_data, name=Path(image_path).name)
                message.attach(image)
            
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            return {"raw": raw_message}
        
        try:
            creds = None
            
            credentials_json_str = os.getenv("GMAIL_CREDENTIALS_JSON")
            token_json_str = os.getenv("GMAIL_TOKEN_JSON")
            print(f"GMAIL_CREDENTIALS_JSON exists: {credentials_json_str is not None}")
            print(f"GMAIL_TOKEN_JSON exists: {token_json_str is not None}")
            
            if credentials_json_str:
                print(f"GMAIL_CREDENTIALS_JSON length: {len(credentials_json_str)} characters")
            if token_json_str:
                print(f"GMAIL_TOKEN_JSON length: {len(token_json_str)} characters")

            if credentials_json_str and token_json_str:
                print("Loading Gmail credentials from secrets...")
                token_info = json.loads(token_json_str)
                creds = Credentials.from_authorized_user_info(token_info, SCOPES)
                
                if creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        print("Token refreshed successfully")
                    except Exception as refresh_error:
                        print(f"Token refresh failed: {refresh_error}")
                        return {
                            "success": False,
                            "message": "Gmail token expired and refresh failed. Please update token in secrets."
                        }
            
            else:
                print("Loading Gmail credentials from local files...")
                token_path = Path("token.json")
                creds_path = Path("credentials.json")
                
                if token_path.exists():
                    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
                
                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        try:
                            creds.refresh(Request())
                        except Exception:
                            if token_path.exists():
                                token_path.unlink()
                            return {
                                "success": False,
                                "message": "Gmail authentication expired. Please restart and re-authenticate."
                            }
                    else:
                        if not creds_path.exists():
                            return {
                                "success": False,
                                "message": "credentials.json not found. Please set up Gmail API credentials."
                            }
                        flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                        creds = flow.run_local_server(port=0)
                    
                    with open(token_path, "w") as token:
                        token.write(creds.to_json())
            
            if not creds or not creds.valid:
                return {
                    "success": False,
                    "message": "Unable to authenticate with Gmail. Please check credentials."
                }
            
            service = build("gmail", "v1", credentials=creds)
            sender = SENDER_EMAIL
            
            image_path = None
            attached_frame = None
            
            if attach_frame_id:
                if attach_frame_id.lower() in ["current", "latest", "last", "this", "that"]:
                    if self.session_captures:
                        most_recent = max(self.session_captures.keys(), 
                                        key=lambda k: self.session_captures[k]['timestamp'])
                        image_path = self.session_captures[most_recent]["filepath"]
                        attached_frame = most_recent
                        print(f"Attaching most recent capture: {most_recent}")
                    elif captured_frames:
                        most_recent = max(captured_frames.keys(), 
                                        key=lambda k: captured_frames[k]['timestamp'])
                        image_path = captured_frames[most_recent]["filepath"]
                        attached_frame = most_recent
                        print(f"Attaching most recent global capture: {most_recent}")
                    else:
                        print(f"No captures available to attach")
                elif attach_frame_id in captured_frames:
                    image_path = captured_frames[attach_frame_id]["filepath"]
                    attached_frame = attach_frame_id
                    print(f"Attaching: {attach_frame_id}")
                else:
                    print(f"Frame '{attach_frame_id}' not found")
            
            if image_path and not Path(image_path).exists():
                print(f"Image file not found: {image_path}")
                image_path = None
            
            message = create_message_with_attachment(sender, recipient, subject, body, image_path)
            send_result = service.users().messages().send(userId="me", body=message).execute()
            
            print(f"Email sent to {recipient}, Message ID: {send_result['id']}")
            if image_path:
                print(f"With attachment: {Path(image_path).name}")
            else:
                print(f"No attachment included")
            
            return {
                "success": True,
                "recipient": recipient,
                "subject": subject,
                "message_id": send_result['id'],
                "attached_image": Path(image_path).name if image_path else None,
                "attached_frame_id": attached_frame,
                "message": f"Email sent to {recipient}" + (f" with attachment {attached_frame}" if attached_frame else " (no attachment)")
            }
            
        except HttpError as error:
            print(f"Gmail API error: {error}")
            return {
                "success": False,
                "message": f"Failed to send email: {str(error)}"
            }
        except Exception as e:
            print(f"Email error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "message": f"Failed to send email: {str(e)}"
            }

    async def capture_and_save_frame(self, frame_id: str, description: Optional[str] = None):
        """Capture and save the current camera view locally"""
        
        async with self.processing_lock:
            try:
                frame_data = self.get_latest_frame()
                
                if not frame_data:
                    return {
                        "success": False,
                        "message": "No camera frame available to capture"
                    }
                
                if frame_id in self.session_captures:
                    existing = self.session_captures[frame_id]
                    time_diff = (datetime.now() - datetime.fromisoformat(existing['timestamp'])).seconds
                    if time_diff < 5:
                        print(f"Skipping duplicate capture: {frame_id} (captured {time_diff}s ago)")
                        return {
                            "success": True,
                            "message": f"Already captured {frame_id} recently",
                            "duplicate": True
                        }
                
                image_data = base64.b64decode(frame_data)
                
                timestamp = datetime.now()
                filename = f"{frame_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
                filepath = CAPTURES_DIR / filename
                
                with open(filepath, "wb") as f:
                    f.write(image_data)
                
                capture_info = {
                    "filename": filename,
                    "filepath": str(filepath),
                    "timestamp": timestamp.isoformat(),
                    "description": description or "No description provided",
                    "status": "captured",
                    "size_bytes": len(image_data)
                }
                
                captured_frames[frame_id] = capture_info
                self.session_captures[frame_id] = capture_info
                
                save_metadata(captured_frames)
                
                if len(captured_frames) > MAX_METADATA_ENTRIES:
                    oldest_key = min(captured_frames.keys(), 
                                   key=lambda k: captured_frames[k]['timestamp'])
                    del captured_frames[oldest_key]
                
                print(f"Frame saved: {filepath} ({len(image_data)} bytes)")
                print(f"Total captures this session: {len(self.session_captures)}")
                
                size_kb = round(len(image_data) / 1024, 2)
                del image_data
                
                return {
                    "success": True,
                    "frame_id": frame_id,
                    "filename": filename,
                    "filepath": str(filepath),
                    "timestamp": timestamp.isoformat(),
                    "size_kb": size_kb,
                    "message": f"Frame captured successfully as {filename}"
                }
                
            except Exception as e:
                print(f"Error saving frame: {e}")
                return {
                    "success": False,
                    "message": f"Failed to save frame: {str(e)}"
                }
    
    async def enable_continuous_monitoring(self, looking_for: Optional[str] = None):
        """Enable continuous monitoring mode"""
        self.session_state.continuous_mode = True
        self.session_state.monitoring_context = looking_for
        print(f"Continuous monitoring enabled. Looking for: {looking_for or 'general observation'}")
        
        return {
            "success": True,
            "message": f"Continuous monitoring enabled" + (f" - Looking for: {looking_for}" if looking_for else ""),
            "context": looking_for
        }
    
    async def disable_continuous_monitoring(self):
        """Disable continuous monitoring mode"""
        self.session_state.continuous_mode = False
        self.session_state.monitoring_context = None
        print("Continuous monitoring disabled")
        
        return {
            "success": True,
            "message": "Continuous monitoring disabled"
        }
    
    async def list_captured_frames(self):
        """List all captured frames"""
        frames_list = []
        for frame_id, info in captured_frames.items():
            filepath = Path(info["filepath"])
            frames_list.append({
                "frame_id": frame_id,
                "filename": info["filename"],
                "timestamp": info["timestamp"],
                "description": info["description"],
                "size_kb": round(info["size_bytes"] / 1024, 2),
                "exists": filepath.exists()
            })
        
        return {
            "success": True,
            "total_frames": len(frames_list),
            "frames": frames_list
        }
    
    async def get_session_summary(self):
        """Get summary of what was captured in this session"""
        return {
            "success": True,
            "session_captures": len(self.session_captures),
            "captures": list(self.session_captures.keys()),
            "details": self.session_captures
        }
    
    async def delete_frame(self, frame_id: str):
        """Delete a captured frame"""
        if frame_id not in captured_frames:
            return {"success": False, "message": f"Frame {frame_id} not found"}
        
        try:
            filepath = Path(captured_frames[frame_id]["filepath"])
            if filepath.exists():
                filepath.unlink()
            del captured_frames[frame_id]
            
            if frame_id in self.session_captures:
                del self.session_captures[frame_id]
            
            save_metadata(captured_frames)
            
            return {"success": True, "message": f"Frame {frame_id} deleted"}
        except Exception as e:
            return {"success": False, "message": f"Failed to delete: {str(e)}"}
    
    async def shutdown_session(self):
        """Gracefully shutdown and save session data"""
        try:
            save_metadata(captured_frames)
            
            summary = {
                "session_end": datetime.now().isoformat(),
                "total_captures": len(self.session_captures),
                "captured_items": list(self.session_captures.keys())
            }
            
            print(f"Session ending gracefully")
            print(f"Total captures this session: {len(self.session_captures)}")
            
            return {
                "success": True,
                "message": "Session ended successfully",
                "summary": summary
            }
        except Exception as e:
            return {"success": False, "message": f"Shutdown error: {str(e)}"}


tools = [
    {
        "function_declarations": [
            {
                "name": "capture_and_save_frame",
                "description": "Capture the current camera view and save it locally. Use ONLY when user explicitly says 'capture', 'save', 'take a picture'. DO NOT call multiple times for one request.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "frame_id": {
                            "type": "string",
                            "description": "Unique identifier (e.g., 'front_door', 'living_room')"
                        },
                        "description": {
                            "type": "string",
                            "description": "Brief description of what's captured"
                        }
                    },
                    "required": ["frame_id"]
                }
            },
            {
                "name": "enable_continuous_monitoring",
                "description": "Enable continuous real-time monitoring mode. Use when user says 'help me find my keys', 'look for my wallet', 'keep watching', 'monitor this', 'help me navigate'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "looking_for": {
                            "type": "string",
                            "description": "What the user is looking for (e.g., 'keys', 'wallet', 'phone', 'exit')"
                        }
                    }
                }
            },
            {
                "name": "disable_continuous_monitoring",
                "description": "Disable continuous monitoring mode. Use when user says 'stop monitoring', 'found it', 'stop looking', 'cancel search'.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "send_email",
                "description": "Send an email with optional image attachment. Use when user says 'email this to me', 'send to my email', 'email this picture'. If user says 'to me' or 'my email', recipient can be omitted (will use default). Can attach previously captured frames.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "recipient": {
                            "type": "string",
                            "description": "Email address of recipient. Use 'me' or omit for default email (user's email)."
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject line"
                        },
                        "body": {
                            "type": "string",
                            "description": "Email body content/message"
                        },
                        "attach_frame_id": {
                            "type": "string",
                            "description": "Optional: frame_id of a previously captured image to attach"
                        }
                    },
                    "required": ["subject", "body"]
                }
            },
            {
                "name": "list_captured_frames",
                "description": "List all saved captures. Use when user says 'what did I capture', 'show my pictures', 'list captures'",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "get_session_summary",
                "description": "Get summary of captures from this session. Use when user asks 'what did I save today', 'show session summary'",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "delete_frame",
                "description": "Delete a saved capture",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "frame_id": {
                            "type": "string",
                            "description": "ID of the frame to delete"
                        }
                    },
                    "required": ["frame_id"]
                }
            },
            {
                "name": "shutdown_session",
                "description": "Gracefully end the session and save all data. Use when user says 'I am done', 'thank you goodbye', 'terminate', 'shut down', 'end session'",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
    }
]


async def execute_tool(tool_instance, tool_name: str, arguments: dict):
    """Execute the requested tool"""
    tools_map = {
        "capture_and_save_frame": tool_instance.capture_and_save_frame,
        "enable_continuous_monitoring": tool_instance.enable_continuous_monitoring,
        "disable_continuous_monitoring": tool_instance.disable_continuous_monitoring,
        "send_email": tool_instance.send_email,
        "list_captured_frames": tool_instance.list_captured_frames,
        "get_session_summary": tool_instance.get_session_summary,
        "delete_frame": tool_instance.delete_frame,
        "shutdown_session": tool_instance.shutdown_session
    }
    
    if tool_name in tools_map:
        return await tools_map[tool_name](**arguments)
    else:
        return {"error": f"Unknown tool: {tool_name}"}


@app.get("/api")
async def root():
    return {
        "name": "Vision Assistant API",
        "status": "running",
        "version": "1.0.0",
        "captures_dir": str(CAPTURES_DIR.absolute()),
        "total_saved_captures": len(captured_frames)
    }


@app.get("/api/health")
async def health():
    return {"status": "healthy"}


@app.get("/api/captures")
async def get_captures():
    """Get list of all captured frames"""
    return {"total": len(captured_frames), "captures": captured_frames}


@app.websocket("/ws/vision")
async def vision_websocket(websocket: WebSocket):
    await websocket.accept()
    print("Client connected")
    
    latest_frame = {"data": None, "timestamp": None}
    session_captures = {}
    session_state = SessionState()
    should_shutdown = False
    websocket_open = True
    
    def get_latest_frame():
        return latest_frame["data"]
    
    tool_instance = VisionAssistantTools(get_latest_frame, session_captures, session_state)
    
    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options={"api_version": "v1beta"}
    )
    
    model = "models/gemini-2.0-flash-live-001"
    
    config = {
        "response_modalities": ["AUDIO"],
        "tools": tools,
        "system_instruction": """You are AIVA - an AI Visual Assistant for visually impaired users and anyone needing visual help.

                                CORE BEHAVIOR:
                                - Speak naturally and conversationally
                                - Be helpful, proactive, and concise
                                - Describe what you see clearly and accurately
                                
                                CONTINUOUS MONITORING MODE:
                                This mode is triggered when the user asks "help me find [item]" or similar requests.
                                You will call enable_continuous_monitoring(looking_for="item") to activate it.
                                
                                MONITORING MODE RULES:
                                1. WHEN YOU SEE THE ITEM:
                                - Say "I FOUND YOUR [ITEM]! It's [specific location]"
                                - Example: "I FOUND YOUR KEYS! They're on the desk next to the coffee mug"
                                - Monitoring will auto-stop after you say "FOUND"
                                
                                2. WHEN YOU DON'T SEE THE ITEM:
                                - Briefly describe what you DO see (5-8 words max)
                                - Example: "Looking at table with books and papers"
                                - Stay focused on finding the requested item
                                
                                3. ADDITIONAL ASSISTANCE:
                                - If monitoring is active and user needs help with OTHER tasks:
                                    • Navigation: "Turn left, stairs ahead, door on right"
                                    • Unboxing: "Cut tape on top, open flaps carefully"
                                    • Step-by-step tasks: Break into simple 3-5 word steps
                                - Prioritize safety-critical information always
                                
                                4. WHEN TO STOP MONITORING:
                                - Automatically after saying "FOUND [ITEM]"
                                - When user says "stop", "thanks", "found it", or "cancel"
                                - When you determine the task is complete
                                - Call disable_continuous_monitoring() to stop
                                
                                5. RESPONSE LENGTH:
                                - Default: 5-8 words during monitoring
                                - Important info: 10-15 words max
                                - Only be verbose for safety warnings or complex instructions
                                
                                CAPTURE AND EMAIL:
                                When user says "email this to me" or "capture and send":
                                1. Call capture_and_save_frame(frame_id="unique_id", description="what's in image")
                                2. Call send_email(recipient="me", attach_frame_id="same_unique_id", subject="...", body="...")
                                
                                SESSION END:
                                When user says "I am done", "goodbye", or "terminate" → call shutdown_session()
                                
                                EXAMPLES:
                                
                                Finding keys:
                                User: "Help me find my keys"
                                You: [call enable_continuous_monitoring] "Looking for your keys"
                                Frame 1: "See table with laptop"
                                Frame 2: "Looking at couch now"
                                Frame 3: "FOUND YOUR KEYS! On the kitchen counter"
                                [monitoring auto-stops]
                                
                                Navigation help while monitoring:
                                User: "Help me navigate to the door"
                                You: "Door is ahead, walk straight 10 feet"
                                [monitoring continues]
                                
                                Unboxing help:
                                User: "How do I open this package?"
                                You: "Cut tape on top. Open flaps. Contents inside."
                                [monitoring continues if active]
                                
                                Be the user's helpful, reliable eyes!"""
    }

    async def safe_send_json(data):
        """Send JSON only if websocket is open"""
        nonlocal websocket_open
        if websocket_open:
            try:
                await websocket.send_json(data)
            except RuntimeError as e:
                if "websocket.close" in str(e) or "already completed" in str(e):
                    websocket_open = False
                    print("WebSocket already closed, stopping sends")
                else:
                    raise

    try:
        async with client.aio.live.connect(model=model, config=config) as session:
            print("Vision Assistant session started")
            print(f"Captures directory: {CAPTURES_DIR.absolute()}")
            
            await safe_send_json({
                "type": "status",
                "message": "Vision Assistant ready!"
            })
            
            async def continuous_monitor():
                """Actively send monitoring prompts WITH current frame every 2 seconds"""
                print("🔍 Monitoring task started")
                
                while websocket_open:
                    try:
                        if session_state.continuous_mode and latest_frame["data"]:
                            time_since_last = (datetime.now() - session_state.last_notification_time).seconds
                            
                            if time_since_last >= 0.5:  # Every .5 seconds
                                item = session_state.monitoring_context or "object"
                                
                                # CRITICAL: Send ONLY the new frame (not accumulated context)
                                print(f"🔍 Sending NEW frame for monitoring check: {item}")
                                
                                # Send the image as inline data in the prompt itself
                                await session.send_client_content(
                                    turns={
                                        "parts": [
                                            {
                                                "inline_data": {
                                                    "mime_type": "image/jpeg",
                                                    "data": latest_frame["data"]
                                                }
                                            },
                                            {
                                                "text": f"Look at THIS image I just sent. Right now. Do you see a {item} in THIS specific image? Answer: If YES → 'FOUND {item.upper()}! Location: [where]' and then stop monitoring immediately. If NO → Not Yet"
                                            }
                                        ]
                                    }
                                )
                                
                                print(f"Monitoring prompt sent with fresh frame for: {item}")
                                session_state.last_notification_time = datetime.now()
                        
                        await asyncio.sleep(2)
                        
                    except asyncio.CancelledError:
                        print("Continuous monitoring task cancelled")
                        break
                    except Exception as e:
                        print(f"Continuous monitoring error: {e}")
                        import traceback
                        traceback.print_exc()
                        await asyncio.sleep(2)

            async def receive_from_gemini():
                nonlocal should_shutdown, websocket_open
                
                current_text = ""
                
                try:
                    while websocket_open:
                        turn = session.receive()
                        async for response in turn:
                            try:
                                if not websocket_open:
                                    break
                                
                                if hasattr(response, 'text') and response.text:
                                    current_text += response.text.lower()
                                    print(f"Text: {response.text}")
                                    
                                    if session_state.continuous_mode:
                                        if "found" in current_text or "FOUND" in current_text:
                                            print(f"FOUND DETECTED - FORCE DISABLING")
                                            
                                            old_item = session_state.monitoring_context
                                            
                                            result = await tool_instance.disable_continuous_monitoring()
                                            print(f"🛑 Disable tool result: {result}")
                                            
                                            await safe_send_json({
                                                "type": "tool_executed",
                                                "tool": "disable_continuous_monitoring",
                                                "result": result
                                            })
                                            
                                            await safe_send_json({
                                                "type": "monitoring_disabled"
                                            })
                                            
                                            await safe_send_json({
                                                "type": "item_found",
                                                "item": old_item
                                            })
                                            
                                            print(f"MONITORING FORCE-STOPPED: {old_item}")
                                            current_text = ""
                                
                                if hasattr(response, 'tool_call') and response.tool_call:
                                    function_responses = []
                                    
                                    for func_call in response.tool_call.function_calls:
                                        tool_name = func_call.name
                                        arguments = dict(func_call.args)
                                        
                                        print(f"Tool: {tool_name} Args: {arguments}")
                                        result = await execute_tool(tool_instance, tool_name, arguments)
                                        
                                        if tool_name == "shutdown_session" and result.get("success"):
                                            should_shutdown = True
                                        
                                        function_response = types.FunctionResponse(
                                            id=func_call.id,
                                            name=func_call.name,
                                            response={"result": result}
                                        )
                                        function_responses.append(function_response)
                                        
                                        await safe_send_json({
                                            "type": "tool_executed",
                                            "tool": tool_name,
                                            "result": result
                                        })
                                        
                                        if tool_name == "enable_continuous_monitoring":
                                            await safe_send_json({
                                                "type": "monitoring_enabled",
                                                "context": arguments.get("looking_for")
                                            })
                                            print(f"Monitoring enabled: {arguments.get('looking_for')}")
                                        elif tool_name == "disable_continuous_monitoring":
                                            await safe_send_json({
                                                "type": "monitoring_disabled"
                                            })
                                            print("Monitoring disabled by tool")
                                    
                                    await session.send_tool_response(function_responses=function_responses)
                                
                                if hasattr(response, 'data') and response.data:
                                    await safe_send_json({
                                        "type": "audio",
                                        "data": response.data.hex()
                                    })
                                
                                if hasattr(response, 'server_content') and response.server_content:
                                    if hasattr(response.server_content, 'turn_complete') and response.server_content.turn_complete:
                                        current_text = ""
                                
                                if should_shutdown:
                                    websocket_open = False
                                    raise asyncio.CancelledError("Shutdown")
                                
                            except Exception as e:
                                if "websocket.close" in str(e):
                                    websocket_open = False
                                    break
                                print(f"Response error: {e}")
                                
                except asyncio.CancelledError:
                    websocket_open = False
                    raise
                except Exception as e:
                    print(f"Receive error: {e}")
                    websocket_open = False

            async def receive_from_client():
                nonlocal websocket_open
                try:
                    while websocket_open:
                        data = await websocket.receive()
                        
                        if "text" in data:
                            message = json.loads(data["text"])
                            
                            if message.get("type") == "text":
                                await session.send_client_content(
                                    turns={"parts": [{"text": message["content"]}]}
                                )
                            elif message.get("type") == "video":
                                latest_frame["data"] = message["data"]
                                latest_frame["timestamp"] = datetime.now()
                                
                                await session.send_realtime_input(
                                    media={
                                        "mime_type": "image/jpeg",
                                        "data": message["data"]
                                    }
                                )
                                
                        elif "bytes" in data:
                            await session.send_realtime_input(
                                media={
                                    "mime_type": "audio/pcm",
                                    "data": data["bytes"]
                                }
                            )
                            
                except WebSocketDisconnect:
                    print("Client disconnected")
                    websocket_open = False
                    return
                except RuntimeError as e:
                    if "disconnect message" in str(e):
                        print("Client disconnected (already closed)")
                        websocket_open = False
                        return
                    raise
                except Exception as e:
                    print(f"Client receive error: {e}")
                    websocket_open = False
                    return

            try:
                await asyncio.gather(
                    receive_from_gemini(),
                    receive_from_client(),
                    continuous_monitor(),  
                    return_exceptions=False
                )
            except (WebSocketDisconnect, asyncio.CancelledError, RuntimeError) as e:
                print(f"Session ended: {type(e).__name__}")
                websocket_open = False
            except Exception as e:
                print(f"Unexpected error: {e}")
                websocket_open = False
    finally:
        websocket_open = False
        save_metadata(captured_frames)
        print(f"Session ended. Captures saved: {len(session_captures)}")
        print(f"Session summary: {list(session_captures.keys())}")
        latest_frame["data"] = None

STATIC_DIR = Path("/app/static")

if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    static_files = STATIC_DIR / "static"
    if static_files.exists():
        app.mount("/static", StaticFiles(directory=str(static_files)), name="static_assets")
    
    @app.get("/")
    async def serve_index():
        return FileResponse(STATIC_DIR / "index.html")
    
    @app.get("/{catchall:path}")
    async def frontend_catchall(catchall: str):
        if catchall.startswith("api") or catchall.startswith("ws"):
            from fastapi import HTTPException
            raise HTTPException(404)
        
        file_path = STATIC_DIR / catchall
        if file_path.is_file():
            return FileResponse(file_path)
        
        return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    print("Starting Vision Assistant Backend...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
