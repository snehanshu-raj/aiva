from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import os
from google import genai

app = FastAPI(title="Vision Assistant API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get API key from environment
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set")

@app.get("/")
async def root():
    return {
        "name": "Vision Assistant API",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.websocket("/ws/vision")
async def vision_websocket(websocket: WebSocket):
    """Main WebSocket endpoint for vision assistance"""
    await websocket.accept()
    print("✓ Client connected")
    
    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options={"api_version": "v1beta"}
    )
    
    model = "models/gemini-2.0-flash-live-001"
    
    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": """You are a helpful vision assistant for visually impaired users. 
        Describe what you see in clear, concise language. Include important details about:
        - Objects and their locations
        - Text you can read
        - People and their activities
        - Obstacles or hazards
        - Colors and spatial relationships
        Be patient, friendly, and provide actionable information."""
    }
    
    try:
        # Use async context manager correctly
        async with client.aio.live.connect(model=model, config=config) as session:
            print("✓ Vision Assistant session started")
            
            # Send welcome message
            await websocket.send_json({
                "type": "status",
                "message": "Vision Assistant ready. Camera is now active."
            })
            
            # Task to receive from Gemini and send to client
            async def receive_from_gemini():
                try:
                    while True:
                        turn = session.receive()
                        async for response in turn:
                            try:
                                if hasattr(response, 'data') and response.data:
                                    # Audio response
                                    await websocket.send_json({
                                        "type": "audio",
                                        "data": response.data.hex()
                                    })
                                
                                if hasattr(response, 'text') and response.text:
                                    # Text response
                                    await websocket.send_json({
                                        "type": "text",
                                        "text": response.text
                                    })
                            except Exception as e:
                                print(f"Response processing error: {e}")
                                
                except asyncio.CancelledError:
                    print("Receive task cancelled")
                    raise
                except Exception as e:
                    print(f"Receive error: {e}")
            
            # Task to receive from client and send to Gemini
            async def receive_from_client():
                try:
                    while True:
                        data = await websocket.receive()
                        
                        if "text" in data:
                            # JSON message
                            message = json.loads(data["text"])
                            
                            if message.get("type") == "text":
                                await session.send(input=message["content"], end_of_turn=True)
                            elif message.get("type") == "video":
                                await session.send(input={
                                    "mime_type": "image/jpeg",
                                    "data": message["data"]
                                })
                                
                        elif "bytes" in data:
                            # Binary audio data
                            await session.send(input={
                                "mime_type": "audio/pcm",
                                "data": data["bytes"]
                            })
                            
                except WebSocketDisconnect:
                    print("✓ Client disconnected")
                    raise
                except Exception as e:
                    print(f"Client receive error: {e}")
                    raise
            
            # Run both tasks concurrently
            async with asyncio.TaskGroup() as tg:
                tg.create_task(receive_from_gemini())
                tg.create_task(receive_from_client())
                
    except* WebSocketDisconnect:
        print("Client disconnected gracefully")
    except* asyncio.CancelledError:
        print("Tasks cancelled")
    # except Exception as e:
    #     print(f"Session error: {e}")
    #     try:
    #         await websocket.send_json({
    #             "type": "error",
    #             "message": f"Session error: {str(e)}"
    #         })
    #     except:
    #         pass

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Vision Assistant Backend...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
