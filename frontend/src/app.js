import React, { useState, useRef, useEffect } from 'react';
import './app.css';
import eyeLogo from './eye.png';

function App() {
  const [isActive, setIsActive] = useState(false);
  const [cameraMode, setCameraMode] = useState('user');
  const [status, setStatus] = useState('Ready to start');
  const [error, setError] = useState(null);
  
  const wsRef = useRef(null);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const audioContextRef = useRef(null);
  const micAudioContextRef = useRef(null);
  const frameIntervalRef = useRef(null);
  const audioQueueRef = useRef([]);
  const isPlayingRef = useRef(false);

  // Start vision assistant
  const startAssistant = async () => {
    try {
      setError(null);
      setStatus('Starting camera...');
      
      // Create AudioContext here after user gesture (critical for mobile)
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext({ sampleRate: 24000 });
        console.log('AudioContext created:', audioContextRef.current.state);
      }
      
      // Request camera and microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: cameraMode,
          width: { ideal: 1280 },
          height: { ideal: 720 }
        },
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true
        }
      });
      
      streamRef.current = stream;
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      
      setStatus('Connecting to assistant...');
      
      // Connect to WebSocket
      const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/vision`;
      const ws = new WebSocket(WS_URL);
      
      ws.onopen = () => {
        setStatus('AIVA is active - Listening and watching');
        setIsActive(true);
        
        // Start sending video frames
        startVideoCapture();
        
        // Start sending audio
        startAudioCapture(stream);
      };
      
      ws.onmessage = async (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'audio') {
          console.log('Audio chunk received, queue length:', audioQueueRef.current.length);
          audioQueueRef.current.push(data.data);
          playNextAudio();
        } else if (data.type === 'tool_executed') {
          setStatus(`✅ ${data.tool} executed successfully`);
          console.log('Tool result:', data.result);
        } else if (data.type === 'status') {
          setStatus(data.message);
        } else if (data.type === 'error') {
          setError(data.message);
        }
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setError('Connection error. Please check backend is running.');
      };
      
      ws.onclose = () => {
        console.log('WebSocket closed');
        setStatus('Disconnected');
        setIsActive(false);
        audioQueueRef.current = [];
        isPlayingRef.current = false;
      };
      
      wsRef.current = ws;
      
    } catch (err) {
      console.error('Start error:', err);
      setError(`Failed to start: ${err.message}`);
      setStatus('Error');
    }
  };

  // Stop vision assistant
  const stopAssistant = () => {
    // Stop video frame capture
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current);
      frameIntervalRef.current = null;
    }
    
    // Stop and close microphone audio context
    if (micAudioContextRef.current) {
      micAudioContextRef.current.close();
      micAudioContextRef.current = null;
    }
    
    // Close playback audio context
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    
    // Stop media stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    
    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    
    // Clear audio queue
    audioQueueRef.current = [];
    isPlayingRef.current = false;
    
    setIsActive(false);
    setStatus('Stopped');
  };

  // Start capturing and sending video frames
  const startVideoCapture = () => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    const ctx = canvas.getContext('2d');
    
    canvas.width = 768;
    canvas.height = 768;
    
    // Send frame every 1 second (1 FPS)
    frameIntervalRef.current = setInterval(() => {
      if (!video.paused && !video.ended && wsRef.current?.readyState === WebSocket.OPEN) {
        // Draw video frame to canvas
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        // Convert to JPEG and send
        canvas.toBlob((blob) => {
          blob.arrayBuffer().then(buffer => {
            const base64 = btoa(
              new Uint8Array(buffer).reduce((data, byte) => data + String.fromCharCode(byte), '')
            );
            
            wsRef.current.send(JSON.stringify({
              type: 'video',
              data: base64
            }));
          });
        }, 'image/jpeg', 0.8);
      }
    }, 1000);
  };

  // Start capturing and sending audio
  const startAudioCapture = (stream) => {
    const audioContext = new AudioContext({ sampleRate: 16000 });
    micAudioContextRef.current = audioContext;
    
    const source = audioContext.createMediaStreamSource(stream);
    const processor = audioContext.createScriptProcessor(1024, 1, 1);
    
    processor.onaudioprocess = (e) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        const audioData = e.inputBuffer.getChannelData(0);
        const int16Array = new Int16Array(audioData.length);
        
        // Convert float32 to int16
        for (let i = 0; i < audioData.length; i++) {
          const s = Math.max(-1, Math.min(1, audioData[i]));
          int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        
        wsRef.current.send(int16Array.buffer);
      }
    };
    
    source.connect(processor);
    processor.connect(audioContext.destination);
  };

  // Play audio response - FIXED FOR MOBILE
  const playNextAudio = async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) {
      return;
    }
    
    isPlayingRef.current = true;
    const hexData = audioQueueRef.current.shift();
    
    try {
      // Use the shared audio context created on button click
      const audioContext = audioContextRef.current;
      
      if (!audioContext) {
        console.error('No AudioContext available');
        isPlayingRef.current = false;
        return;
      }
      
      // CRITICAL FOR MOBILE: Resume if suspended
      if (audioContext.state === 'suspended') {
        console.log('Resuming suspended AudioContext');
        await audioContext.resume();
      }
      
      // Convert hex to bytes
      const bytes = new Uint8Array(
        hexData.match(/.{1,2}/g).map(byte => parseInt(byte, 16))
      );
      
      const int16Array = new Int16Array(bytes.buffer);
      const float32Array = new Float32Array(int16Array.length);
      
      // Convert int16 to float32
      for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / 32768.0;
      }
      
      const audioBuffer = audioContext.createBuffer(1, float32Array.length, 24000);
      audioBuffer.getChannelData(0).set(float32Array);
      
      const source = audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContext.destination);
      
      source.onended = () => {
        isPlayingRef.current = false;
        playNextAudio(); // Play next in queue
      };
      
      source.start();
    } catch (err) {
      console.error('Audio playback error:', err);
      isPlayingRef.current = false;
      
      // Try next chunk after error
      setTimeout(() => {
        playNextAudio();
      }, 50);
    }
  };

  // Switch camera
  const switchCamera = async () => {
    if (isActive) {
      stopAssistant();
      const newMode = cameraMode === 'user' ? 'environment' : 'user';
      setCameraMode(newMode);
      // Wait a bit then restart with new camera
      setTimeout(() => {
        startAssistant();
      }, 500);
    } else {
      setCameraMode(cameraMode === 'user' ? 'environment' : 'user');
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopAssistant();
    };
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <h1>👁️ AIVA</h1>
        <p className="subtitle">Real-time AI Visual Assistant</p>
      </header>

      {!isActive && (
        <div className="landing-animation">
          <img 
            src={eyeLogo}
            alt="AIVA Eye" 
            className="eye-logo" 
          />
        </div>
      )}

      <main className="main-content">
        {error && (
          <div className="error-banner" role="alert">
            <strong>Error:</strong> {error}
          </div>
        )}

        <div className="status-bar">
          <span className={`status-indicator ${isActive ? 'active' : ''}`}>
            {isActive ? '🟢' : '⚫'}
          </span>
          <span className="status-text">{status}</span>
        </div>

        <div className={`video-container ${isActive ? 'active' : ''}`}>
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="video-preview"
          />
          <canvas ref={canvasRef} style={{ display: 'none' }} />
        </div>

        <footer className="App-footer">
          <p>🎤 Speak naturally - the assistant will describe what it sees and answer your questions!</p>
        </footer>

        <div className="controls">
          <button
            className="camera-switch-btn"
            onClick={switchCamera}
            aria-label={`Switch to ${cameraMode === 'user' ? 'rear' : 'front'} camera`}
          >
            {cameraMode === 'user' ? '📱 Front Camera Active' : '📷 Rear Camera Active'}
          </button>

          {!isActive ? (
            <button
              className="start-btn"
              onClick={startAssistant}
              aria-label="Start vision assistant"
            >
              ▶️ Wake AIVA
            </button>
          ) : (
            <button
              className="stop-btn"
              onClick={stopAssistant}
              aria-label="Stop vision assistant"
            >
              ⏹️ Sleep AIVA
            </button>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
