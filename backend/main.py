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
import sys
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
            print(f"⚠️ Could not load metadata: {e}")
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

class VisionAssistantTools:
    """Tools that can be called via voice commands"""
    def __init__(self, get_latest_frame_callback, session_captures):
        self.get_latest_frame = get_latest_frame_callback
        self.session_captures = session_captures  
        self.processing_lock = asyncio.Lock()  
        
    async def send_email(self, recipient: Optional[str] = None, subject: str = "Vision Assistant Capture", body: str = "Here's the image you requested.", attach_frame_id: Optional[str] = None):
        """Send email with optional image attachment using Gmail API"""
        
        # Use default email if recipient not specified
        if not recipient or recipient.lower() in ["me", "myself", "my email"]:
            recipient = DEFAULT_EMAIL
        
        SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
        
        def create_message_with_attachment(sender, to, subject, body_text, image_path=None):
            """Create email message with optional image attachment"""
            message = MIMEMultipart()
            message["to"] = to
            message["from"] = sender
            message["subject"] = subject
            
            # Add body
            msg = MIMEText(body_text)
            message.attach(msg)
            
            # Add image attachment if provided
            if image_path and Path(image_path).exists():
                with open(image_path, 'rb') as f:
                    img_data = f.read()
                image = MIMEImage(img_data, name=Path(image_path).name)
                message.attach(image)
            
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            return {"raw": raw_message}
        
        try:
            creds = None
            
            # Try to load from environment variables (Cloud Run secrets)
            credentials_json_str = os.getenv("GMAIL_CREDENTIALS_JSON")
            token_json_str = os.getenv("GMAIL_TOKEN_JSON")
            
            # If secrets exist, use them (Cloud Run)
            if credentials_json_str and token_json_str:
                print("📧 Loading Gmail credentials from secrets...")
                
                # Parse token JSON
                token_info = json.loads(token_json_str)
                creds = Credentials.from_authorized_user_info(token_info, SCOPES)
                
                # Refresh if expired
                if creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        print("✅ Token refreshed successfully")
                    except Exception as refresh_error:
                        print(f"⚠️ Token refresh failed: {refresh_error}")
                        return {
                            "success": False,
                            "message": "Gmail token expired and refresh failed. Please update token in secrets."
                        }
            
            # Fallback to local files (development mode)
            else:
                print("📧 Loading Gmail credentials from local files...")
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
            
            # Check if we have valid credentials
            if not creds or not creds.valid:
                return {
                    "success": False,
                    "message": "Unable to authenticate with Gmail. Please check credentials."
                }
            
            # Build Gmail service
            service = build("gmail", "v1", credentials=creds)
            sender = SENDER_EMAIL
            
            # Determine which image to attach
            image_path = None
            attached_frame = None
            
            if attach_frame_id:
                # Handle special keywords
                if attach_frame_id.lower() in ["current", "latest", "last", "this", "that"]:
                    if self.session_captures:
                        most_recent = max(self.session_captures.keys(), 
                                        key=lambda k: self.session_captures[k]['timestamp'])
                        image_path = self.session_captures[most_recent]["filepath"]
                        attached_frame = most_recent
                        print(f"📎 Attaching most recent capture: {most_recent}")
                    elif captured_frames:
                        most_recent = max(captured_frames.keys(), 
                                        key=lambda k: captured_frames[k]['timestamp'])
                        image_path = captured_frames[most_recent]["filepath"]
                        attached_frame = most_recent
                        print(f"📎 Attaching most recent global capture: {most_recent}")
                    else:
                        print(f"⚠️ No captures available to attach")
                elif attach_frame_id in captured_frames:
                    image_path = captured_frames[attach_frame_id]["filepath"]
                    attached_frame = attach_frame_id
                    print(f"📎 Attaching: {attach_frame_id}")
                else:
                    print(f"⚠️ Frame '{attach_frame_id}' not found")
            
            # Verify image file exists
            if image_path and not Path(image_path).exists():
                print(f"⚠️ Image file not found: {image_path}")
                image_path = None
            
            # Create and send message
            message = create_message_with_attachment(sender, recipient, subject, body, image_path)
            send_result = service.users().messages().send(userId="me", body=message).execute()
            
            print(f"📧 Email sent to {recipient}, Message ID: {send_result['id']}")
            if image_path:
                print(f"✅ With attachment: {Path(image_path).name}")
            else:
                print(f"⚠️ No attachment included")
            
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
            print(f"❌ Gmail API error: {error}")
            return {
                "success": False,
                "message": f"Failed to send email: {str(error)}"
            }
        except Exception as e:
            print(f"❌ Email error: {e}")
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
                    if time_diff < 5:  # Within 5 seconds
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
                
                print(f"📸 Frame saved: {filepath} ({len(image_data)} bytes)")
                print(f"💾 Total captures this session: {len(self.session_captures)}")
                
                size_kb = round(len(image_data) / 1024, 2)
                del image_data  # Free memory
                
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
            
            # Also remove from session captures
            if frame_id in self.session_captures:
                del self.session_captures[frame_id]
            
            # Save updated metadata
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
    
    latest_frame = {"data": None}
    session_captures = {} 
    should_shutdown = False
    
    def get_latest_frame():
        return latest_frame["data"]
    
    tool_instance = VisionAssistantTools(get_latest_frame, session_captures)
    
    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options={"api_version": "v1beta"}
    )
    
    model = "models/gemini-2.0-flash-live-001"
    
    config = {
        "response_modalities": ["AUDIO"],
        "tools": tools,
        "system_instruction": """You are a helpful vision assistant for visually impaired users.

                                CRITICAL WORKFLOW FOR "CAPTURE AND EMAIL":
                                When user says "email this to me" or "email this picture to me" or just "capture this and email this picture to me":
                                1. FIRST: Call capture_and_save_frame with a unique frame_id (e.g., "capture_001")
                                2. SECOND: Call send_email with attach_frame_id set to the SAME frame_id from step 1
                                Always capture the image and send it in email.

                                When user says "email this to me" WITHOUT capturing first:
                                - Use attach_frame_id="latest" to attach the most recent capture

                                RULES:
                                1. Call capture_and_save_frame ONLY ONCE per request
                                2. Do NOT call tools multiple times
                                3. For "I am done" → call shutdown_session
                                4. For email:
                                - "to me" or "my email" → omit recipient or use "me"
                                - Specific email → use that address
                                - Fill subject and body intelligently if not provided

                                Your capabilities:
                                - Describe what you see
                                - Capture and save views
                                - Send emails with images
                                - List/delete captures
                                - Graceful shutdown

                                Example:
                                User: "Capture this and email it to me"
                                Step 1: capture_and_save_frame(frame_id="view_123", description="...")
                                Step 2: send_email(recipient="me", attach_frame_id="view_123", subject="...", body="...")

                                User: "Email this to me"
                                Step 1: send_email(recipient="me", attach_frame_id="latest", subject="...", body="...")

                                Be precise with frame_ids!"""

    }

    try:
        async with client.aio.live.connect(model=model, config=config) as session:
            print("Vision Assistant session started")
            print(f"📁 Captures directory: {CAPTURES_DIR.absolute()}")
            
            await websocket.send_json({
                "type": "status",
                "message": "Vision Assistant ready!"
            })
            
            async def receive_from_gemini():
                nonlocal should_shutdown
                
                try:
                    while True:
                        turn = session.receive()
                        async for response in turn:
                            try:
                                # Handle tool calls
                                if hasattr(response, 'tool_call') and response.tool_call:
                                    function_responses = []
                                    
                                    for func_call in response.tool_call.function_calls:
                                        tool_name = func_call.name
                                        arguments = dict(func_call.args)
                                        
                                        print(f"🔧 Tool called: {tool_name}")
                                        print(f"   Arguments: {arguments}")
                                        
                                        # Execute the tool
                                        result = await execute_tool(tool_instance, tool_name, arguments)
                                        
                                        # Check if shutdown was requested
                                        if tool_name == "shutdown_session" and result.get("success"):
                                            should_shutdown = True
                                        
                                        # Create FunctionResponse
                                        function_response = types.FunctionResponse(
                                            id=func_call.id,
                                            name=func_call.name,
                                            response={"result": result}
                                        )
                                        function_responses.append(function_response)
                                        
                                        # Notify frontend
                                        await websocket.send_json({
                                            "type": "tool_executed",
                                            "tool": tool_name,
                                            "result": result
                                        })
                                    
                                    # Send tool responses back
                                    await session.send_tool_response(
                                        function_responses=function_responses
                                    )
                                
                                # Handle audio responses
                                if hasattr(response, 'data') and response.data:
                                    await websocket.send_json({
                                        "type": "audio",
                                        "data": response.data.hex()
                                    })
                                
                                # If shutdown requested, break after response
                                if should_shutdown:
                                    print("🛑 Shutdown requested, ending session...")
                                    await websocket.send_json({
                                        "type": "shutdown",
                                        "message": "Session ending gracefully"
                                    })
                                    await asyncio.sleep(2)  # Give time for final audio
                                    raise asyncio.CancelledError("Graceful shutdown")
                                
                            except Exception as e:
                                print(f"❌ Response processing error: {e}")
                                import traceback
                                traceback.print_exc()
                                
                except asyncio.CancelledError:
                    print("Receive task cancelled (graceful shutdown)")
                    raise
                except Exception as e:
                    print(f"❌ Receive error: {e}")
            
            async def receive_from_client():
                try:
                    while True:
                        data = await websocket.receive()
                        
                        if "text" in data:
                            message = json.loads(data["text"])
                            
                            if message.get("type") == "text":
                                await session.send_client_content(
                                    turns={"parts": [{"text": message["content"]}]}
                                )
                            elif message.get("type") == "video":
                                # Store latest frame (replaces previous)
                                latest_frame["data"] = message["data"]
                                
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
                    return
                except RuntimeError as e:
                    if "disconnect message" in str(e):
                        print("Client disconnected (already closed)")
                        return
                    raise
                except Exception as e:
                    print(f"Client receive error: {e}")
                    return

            try:
                await asyncio.gather(
                    receive_from_gemini(),
                    receive_from_client(),
                    return_exceptions=False
                )
            except (WebSocketDisconnect, asyncio.CancelledError, RuntimeError) as e:
                print(f"Session ended: {type(e).__name__}")
            except Exception as e:
                print(f"Unexpected error: {e}")
    finally:
        save_metadata(captured_frames)
        print(f"✅ Session ended. Captures saved: {len(session_captures)}")
        print(f"📋 Session summary: {list(session_captures.keys())}")
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
