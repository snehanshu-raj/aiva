import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Camera, Mic, Image as ImageIcon, X, Power, Map as MapIcon, RefreshCw } from 'lucide-react';
import Gallery from './components/Gallery';
import MapGallery from './components/MapGallery';
import './app.css';
import saforiaLogo from './saforia.png';

// Separate component to handle video lifecycle reliably
const CameraView = ({ stream, onMount, isMonitoring, status, onSwitchCamera, onStop }) => {
  const videoRef = useRef(null);

  useEffect(() => {
    if (videoRef.current && stream) {
      console.log("CameraView mounted, attaching stream");
      videoRef.current.srcObject = stream;
      videoRef.current.play().catch(e => console.error("Play error:", e));

      // Notify parent that video is ready for capture
      if (onMount) {
        onMount(videoRef.current);
      }
    }
  }, [stream, onMount]);

  return (
    <motion.div
      className="video-container"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      key="camera"
    >
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className="video-preview"
      />

      <div className="controls-overlay">
        <div className="status-badge">
          <div className={`status-dot ${isMonitoring ? 'monitoring' : 'active'}`} />
          {status}
        </div>

        <div className="secondary-controls">
          <button className="icon-btn" onClick={onSwitchCamera}>
            <RefreshCw size={24} />
          </button>
          <button className="icon-btn danger" onClick={onStop}>
            <X size={24} />
          </button>
        </div>

        <div className="voice-hint">
          <Mic size={12} style={{ display: 'inline', marginRight: 4 }} />
          Say "Exit" to stop
        </div>
      </div>
    </motion.div>
  );
};

function App() {
  const [isActive, setIsActive] = useState(false);
  const [cameraMode, setCameraMode] = useState('user');
  const [status, setStatus] = useState('Ready to start');
  const [error, setError] = useState(null);
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [showGallery, setShowGallery] = useState(false);
  const [showMap, setShowMap] = useState(false);
  const [captures, setCaptures] = useState([]);

  // Fetch captures from backend
  const fetchCaptures = async () => {
    try {
      const response = await fetch('/api/captures');
      const data = await response.json();
      if (data.captures) {
        // Convert dictionary to array, preserving the frame_id (key)
        const capturesList = Object.entries(data.captures).map(([key, value]) => ({
          ...value,
          frame_id: key
        }));

        // Sort by timestamp descending
        const sorted = capturesList.sort((a, b) =>
          new Date(b.timestamp) - new Date(a.timestamp)
        );
        setCaptures(sorted);
      }
    } catch (e) {
      console.error("Failed to fetch captures:", e);
    }
  };

  const deleteCapture = async (id) => {
    try {
      const response = await fetch(`/api/captures/${id}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        // Optimistic update
        setCaptures(prev => prev.filter(c => c.frame_id !== id));
        // Also refresh to be sure
        fetchCaptures();
      } else {
        console.error("Failed to delete capture");
      }
    } catch (e) {
      console.error("Error deleting capture:", e);
    }
  };

  // Initial fetch
  useEffect(() => {
    fetchCaptures();
  }, []);

  const wsRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const audioContextRef = useRef(null);
  const micAudioContextRef = useRef(null);
  const frameIntervalRef = useRef(null);
  const audioQueueRef = useRef([]);
  const isPlayingRef = useRef(false);
  const recognitionRef = useRef(null);
  const locationWatchIdRef = useRef(null);
  const lastKnownPositionRef = useRef(null);

  // We keep track of the active video element for capture
  const activeVideoRef = useRef(null);
  const shouldRestartRecognitionRef = useRef(true);

  // Handle location requests and updates
  useEffect(() => {
    if (!navigator.geolocation) {
      console.log("Geolocation is not supported by this browser.");
      return;
    }

    const sendLocationUpdate = (position, type = 'location_update') => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        const locationData = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
          timestamp: position.timestamp
        };

        wsRef.current.send(JSON.stringify({
          type: type,
          location: locationData
        }));
        console.log(`Sent ${type}:`, locationData);
      }
    };

    // Watch position for continuous updates
    locationWatchIdRef.current = navigator.geolocation.watchPosition(
      (position) => {
        // Cache the latest position
        lastKnownPositionRef.current = position;

        // Send update if we have a connection
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          sendLocationUpdate(position, 'location_update');
        }
      },
      (error) => console.error("Location watch error:", error),
      { enableHighAccuracy: true, maximumAge: 30000, timeout: 27000 }
    );

    return () => {
      if (locationWatchIdRef.current) {
        navigator.geolocation.clearWatch(locationWatchIdRef.current);
      }
    };
  }, []);

  // Keep track of camera mode for voice commands without re-triggering effect
  const cameraModeRef = useRef(cameraMode);
  useEffect(() => {
    cameraModeRef.current = cameraMode;
  }, [cameraMode]);

  // Initialize Speech Recognition
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = false;
      recognition.lang = 'en-US';
      recognition.onresult = (event) => {
        const lastResult = event.results[event.results.length - 1];
        const command = lastResult[0].transcript.trim().toLowerCase();
        console.log('Voice command received:', command);

        let targetMode = 'user';
        let specificRequest = false;
        let isCameraCommand = false;

        if (command.includes('open back camera') || command.includes('start back camera') || command.includes('open rear camera') || command.includes('start rear camera') || command.includes('open environment camera') || command.includes('start environment camera')) {
          targetMode = 'environment';
          specificRequest = true;
          isCameraCommand = true;
        } else if (command.includes('open front camera') || command.includes('start front camera') || command.includes('open user camera') || command.includes('start user camera') || command.includes('open face camera') || command.includes('start face camera')) {
          targetMode = 'user';
          specificRequest = true;
          isCameraCommand = true;
        } else if (command.includes('open camera') || command.includes('start camera')) {
          // Generic "open camera" command, default to user mode, not specific request
          targetMode = 'user';
          specificRequest = false;
          isCameraCommand = true;
        }

        if (isCameraCommand) {
          if (!isActive) {
            // Stop recognition to avoid microphone conflict on mobile
            if (recognitionRef.current) {
              shouldRestartRecognitionRef.current = false;
              recognitionRef.current.stop();
            }
            // If specific request, use it. If generic, default to user (front)
            const modeToUse = specificRequest ? targetMode : 'user';
            console.log(`Starting assistant via voice (Mode: ${modeToUse})`);
            startAssistant(modeToUse);
          } else {
            // Already active. Check if we need to switch.
            const currentMode = cameraModeRef.current;
            if (specificRequest && targetMode !== currentMode) {
              console.log(`Switching to ${targetMode} via voice`);
              stopAssistant();
              setCameraMode(targetMode);
              setTimeout(() => {
                startAssistant(targetMode);
              }, 500);
            }
          }
        } else if (command.includes('exit') || command.includes('stop camera') || command.includes('close camera')) {
          if (isActive) {
            console.log("Stopping assistant via voice");
            stopAssistant();
          }
        } else if (command.includes('open gallery') || command.includes('show gallery') || command.includes('view gallery')) {
          console.log("Opening gallery via voice");
          setShowGallery(true);
          setShowMap(false);
        } else if (command.includes('open map') || command.includes('show map') || command.includes('view map')) {
          console.log("Opening map via voice");
          setShowMap(true);
          setShowGallery(false);
        } else if (command.includes('close gallery') || command.includes('hide gallery') ||
          command.includes('close map') || command.includes('hide map') ||
          command.includes('go home') || command.includes('go back') || command.includes('main menu')) {
          console.log("Navigating home via voice");
          setShowGallery(false);
          setShowMap(false);
        }
      };

      recognition.onend = () => {
        console.log('Speech recognition ended');
        // Auto-restart if we didn't intentionally stop it (e.g., to start camera)
        if (shouldRestartRecognitionRef.current && !isActive) {
          console.log('Restarting speech recognition...');
          try {
            if (!recognition.recognizing) {
              recognition.start();
            } else {
              console.log('Recognition already active, not restarting.');
            }
          } catch (e) {
            console.log('Could not restart recognition:', e);
          }
        }
      };

      recognition.onerror = (event) => {
        if (event.error !== 'no-speech') {
          console.error('Speech recognition error', event.error);
        }
      };

      recognitionRef.current = recognition;

      try {
        shouldRestartRecognitionRef.current = true;
        if (!isActive) {
          recognition.start();
        }
      } catch (e) {
        console.log('Recognition already started or not allowed yet');
      }
    }

    return () => {
      if (recognitionRef.current) {
        shouldRestartRecognitionRef.current = false;
        recognitionRef.current.stop();
      }
    };
  }, [isActive]);

  // Capture helper
  // const captureImage = (description) => {
  //   if (activeVideoRef.current && canvasRef.current) {
  //     const canvas = canvasRef.current;
  //     const video = activeVideoRef.current;
  //     canvas.width = video.videoWidth;
  //     canvas.height = video.videoHeight;
  //     canvas.getContext('2d').drawImage(video, 0, 0);

  //     const image = canvas.toDataURL('image/jpeg');
  //     const newCapture = {
  //       id: Date.now(),
  //       image,
  //       description: description || 'Captured moment',
  //       timestamp: Date.now()
  //     };

  //     setCaptures(prev => [newCapture, ...prev]);
  //   }
  // };

  // Start vision assistant
  const startAssistant = async (preferredMode = null) => {
    if (isActive) return;

    // Sanitize preferredMode (it might be an event object if called from onClick)
    const targetMode = (typeof preferredMode === 'string') ? preferredMode : null;

    try {
      setError(null);
      setStatus('Starting camera...');

      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext({ sampleRate: 24000 });
      }

      // Use preferred mode if specified, otherwise use state from ref (to avoid stale closure)
      const modeToUse = targetMode || cameraModeRef.current || 'user';

      // Update state to match what we're actually using
      if (targetMode) {
        setCameraMode(targetMode);
      }

      const audioConstraints = {
        channelCount: 1,
        sampleRate: 16000,
        echoCancellation: true,
        noiseSuppression: true
      };

      let stream;
      try {
        // Try with exact constraints first if environment is requested
        // This is required on many mobile devices to force the back camera
        const videoConstraints = {
          width: { ideal: 1280 },
          height: { ideal: 720 }
        };

        if (modeToUse === 'environment') {
          videoConstraints.facingMode = { exact: 'environment' };
        } else {
          videoConstraints.facingMode = modeToUse;
        }

        console.log(`Requesting camera with constraints:`, videoConstraints);
        stream = await navigator.mediaDevices.getUserMedia({
          video: videoConstraints,
          audio: audioConstraints
        });
      } catch (err) {
        console.warn(`Failed with specific constraints (${err.name}), trying fallback...`);

        // Fallback to simple ideal constraint
        stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: modeToUse,
            width: { ideal: 1280 },
            height: { ideal: 720 }
          },
          audio: audioConstraints
        });
      }

      console.log("Camera stream obtained", stream);
      streamRef.current = stream;
      setIsActive(true);
      setStatus('Connecting to assistant...');

      const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/vision`;
      const ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        setStatus('Agent is active');
        startAudioCapture(stream);
        // Video capture will be started by the CameraView callback
      };

      ws.onmessage = async (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'audio') {
          audioQueueRef.current.push(data.data);
          playNextAudio();
        } else if (data.type === 'shutdown_session') {
          console.log("Received shutdown signal from backend");
          setStatus('Session ended by assistant');
          stopAssistant();
        } else if (data.type === 'tool_executed') {
          setStatus(`✅ ${data.tool} executed`);

          if (data.tool === 'shutdown_session') {
            console.log("Received shutdown tool execution");
            setStatus('Session ended by assistant');
            stopAssistant();
          }

          // Restore capture ONLY for the explicit capture tool
          if (data.tool === 'capture_and_save_frame') {
            setStatus('✅ Image captured & saved');
            // Refresh gallery
            fetchCaptures();
          }
        } else if (data.type === 'status') {
          setStatus(data.message);
        } else if (data.type === 'error') {
          setError(data.message);
        } else if (data.type === 'monitoring_enabled') {
          setIsMonitoring(true);
          setStatus('🔍 Monitoring active');
        } else if (data.type === 'monitoring_disabled') {
          setIsMonitoring(false);
          setStatus('Saforia is active');
        } else if (data.type === 'request_location') {
          console.log("📍 Backend requested location - Starting geolocation...");
          setStatus('📍 Locating...');

          // Strategy 1: Check for cached position first (if less than 60s old)
          if (lastKnownPositionRef.current) {
            const age = Date.now() - lastKnownPositionRef.current.timestamp;
            if (age < 1000) {
              console.log(`✅ Using cached location (${Math.round(age / 1000)}s old)`);
              const position = lastKnownPositionRef.current;
              const locationData = {
                latitude: position.coords.latitude,
                longitude: position.coords.longitude,
                accuracy: position.coords.accuracy,
                timestamp: position.timestamp
              };

              wsRef.current.send(JSON.stringify({
                type: 'location_response',
                location: locationData
              }));
              setStatus('📍 Location sent (Cached)');
              setTimeout(() => setStatus('Saforia is active'), 10000);
              return;
            }
          }

          if (!navigator.geolocation) {
            console.error("❌ Geolocation NOT supported by this browser");
            wsRef.current.send(JSON.stringify({
              type: 'location_response',
              error: "Geolocation not supported"
            }));
            return;
          }

          // Strategy 2: Fresh High Accuracy Request
          navigator.geolocation.getCurrentPosition(
            (position) => {
              console.log("✅ Fresh Location obtained:", position.coords);
              lastKnownPositionRef.current = position; // Update cache

              const locationData = {
                latitude: position.coords.latitude,
                longitude: position.coords.longitude,
                accuracy: position.coords.accuracy,
                timestamp: position.timestamp
              };

              wsRef.current.send(JSON.stringify({
                type: 'location_response',
                location: locationData
              }));
              setStatus('📍 Location sent');
              setTimeout(() => setStatus('Saforia is active'), 10000);
            },
            (error) => {
              console.warn("⚠️ High accuracy location failed, trying low accuracy...", error.message);

              // Strategy 3: Fallback to Low Accuracy
              navigator.geolocation.getCurrentPosition(
                (position) => {
                  console.log("✅ Low Accuracy Location obtained:", position.coords);
                  lastKnownPositionRef.current = position;

                  const locationData = {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    accuracy: position.coords.accuracy,
                    timestamp: position.timestamp
                  };

                  wsRef.current.send(JSON.stringify({
                    type: 'location_response',
                    location: locationData
                  }));
                  setStatus('📍 Location sent (Low Acc)');
                  setTimeout(() => setStatus('Saforia is active'), 10000);
                },
                (fallbackError) => {
                  console.error("❌ All location attempts failed:", fallbackError.message);
                  wsRef.current.send(JSON.stringify({
                    type: 'location_response',
                    error: fallbackError.message
                  }));
                  setStatus('❌ Location failed');
                },
                { enableHighAccuracy: false, timeout: 10000, maximumAge: 0 }
              );
            },
            { enableHighAccuracy: true, timeout: 5000, maximumAge: 0 }
          );
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setError('Connection error. Please check backend.');
      };

      ws.onclose = () => {
        setStatus('Disconnected');
        if (isActive) {
          stopAssistant(); // Ensure full cleanup
        }
      };

      wsRef.current = ws;

    } catch (err) {
      console.error('Start error:', err);
      setError(`Failed to start: ${err.message}`);
      setStatus('Error');
      setIsActive(false);
    }
  };

  // Stop vision assistant
  const stopAssistant = () => {
    console.log("Stopping assistant...");

    if (audioContextRef.current) {
      try {
        audioContextRef.current.suspend();
        audioContextRef.current.close();
      } catch (e) { console.error("Audio close error", e); }
      audioContextRef.current = null;
    }

    audioQueueRef.current = [];
    isPlayingRef.current = false;

    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current);
      frameIntervalRef.current = null;
    }

    if (micAudioContextRef.current) {
      try {
        micAudioContextRef.current.close();
      } catch (e) { console.error("Mic close error", e); }
      micAudioContextRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsActive(false);
    setIsMonitoring(false);
    setStatus('Stopped');
    activeVideoRef.current = null;
  };

  // Callback when CameraView is ready
  const handleCameraMount = (videoElement) => {
    console.log("CameraView reported ready");
    activeVideoRef.current = videoElement;
    startVideoCapture(videoElement);
  };

  // Start capturing and sending video frames
  const startVideoCapture = (videoElement) => {
    const canvas = canvasRef.current;
    const video = videoElement || activeVideoRef.current;

    if (!canvas || !video) {
      console.error("Canvas or video not available for capture");
      return;
    }

    const ctx = canvas.getContext('2d');
    canvas.width = 768;
    canvas.height = 768;

    // Clear any existing interval
    if (frameIntervalRef.current) clearInterval(frameIntervalRef.current);

    frameIntervalRef.current = setInterval(() => {
      if (video.readyState >= 2 && !video.paused && !video.ended && wsRef.current?.readyState === WebSocket.OPEN) {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

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

  // Play audio response
  const playNextAudio = async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) {
      return;
    }

    isPlayingRef.current = true;
    const hexData = audioQueueRef.current.shift();

    try {
      const audioContext = audioContextRef.current;

      if (!audioContext) {
        isPlayingRef.current = false;
        return;
      }

      if (audioContext.state === 'suspended') {
        await audioContext.resume();
      }

      const bytes = new Uint8Array(
        hexData.match(/.{1,2}/g).map(byte => parseInt(byte, 16))
      );

      const int16Array = new Int16Array(bytes.buffer);
      const float32Array = new Float32Array(int16Array.length);

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
        playNextAudio();
      };

      source.start();
    } catch (err) {
      console.error('Audio playback error:', err);
      isPlayingRef.current = false;
      setTimeout(() => {
        playNextAudio();
      }, 50);
    }
  };

  const switchCamera = async () => {
    if (isActive) {
      try {
        const newMode = cameraMode === 'user' ? 'environment' : 'user';
        console.log(`Switching to ${newMode} camera...`);

        const audioConstraints = {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true
        };

        let newStream;
        try {
          const videoConstraints = {
            width: { ideal: 1280 },
            height: { ideal: 720 }
          };

          if (newMode === 'environment') {
            videoConstraints.facingMode = { exact: 'environment' };
          } else {
            videoConstraints.facingMode = newMode;
          }

          newStream = await navigator.mediaDevices.getUserMedia({
            video: videoConstraints,
            audio: audioConstraints
          });
        } catch (err) {
          console.warn(`Failed with specific constraints, trying fallback...`);
          newStream = await navigator.mediaDevices.getUserMedia({
            video: {
              facingMode: newMode,
              width: { ideal: 1280 },
              height: { ideal: 720 }
            },
            audio: audioConstraints
          });
        }

        // Stop old tracks
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop());
        }

        // Update ref
        streamRef.current = newStream;

        // Restart Audio Capture
        if (micAudioContextRef.current) {
          try {
            micAudioContextRef.current.close();
          } catch (e) { console.error("Mic close error", e); }
          micAudioContextRef.current = null;
        }
        startAudioCapture(newStream);

        // Update state to trigger CameraView update
        setCameraMode(newMode);

      } catch (err) {
        console.error("Failed to switch camera:", err);
        setError("Failed to switch camera");
      }
    } else {
      setCameraMode(cameraMode === 'user' ? 'environment' : 'user');
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <div className="brand">
          <Camera className="logo-icon" size={24} />
          <h1>Saforia</h1>
        </div>
        <button
          className="gallery-btn"
          onClick={() => setShowMap(true)}
          aria-label="Open Map"
          style={{ marginRight: '10px' }}
        >
          <MapIcon size={24} />
        </button>
        <button
          className="gallery-btn"
          onClick={() => setShowGallery(true)}
          aria-label="Open Gallery"
        >
          <ImageIcon size={24} />
        </button>
      </header>

      <main className="main-content">
        <AnimatePresence mode="wait">
          {!isActive ? (
            <motion.div
              className="landing-content"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              key="landing"
            >
              <div className="saforia-container">
                <div className="pulse-ring"></div>
                <img src={saforiaLogo} alt="Saforia Eye" className="saforia-logo" />
              </div>

              <button className="primary-btn" onClick={startAssistant}>
                <Power size={20} />
              </button>

              <div className="voice-hint">
                <Mic size={12} style={{ display: 'inline', marginRight: 4 }} />
                Say "Open Back Camera" to start
              </div>
            </motion.div>
          ) : (
            <CameraView
              stream={streamRef.current}
              onMount={handleCameraMount}
              isMonitoring={isMonitoring}
              status={status}
              onSwitchCamera={switchCamera}
              onStop={stopAssistant}
            />
          )}
        </AnimatePresence>
      </main>

      {/* Hidden canvas for capture */}
      <canvas ref={canvasRef} style={{ display: 'none' }} />

      <AnimatePresence>
        {showGallery && (
          <Gallery
            captures={captures}
            onClose={() => setShowGallery(false)}
            onRefresh={fetchCaptures}
            onDelete={deleteCapture}
          />
        )}
        {showMap && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{ position: 'fixed', inset: 0, zIndex: 9999 }}
          >
            <MapGallery
              captures={captures}
              currentLocation={lastKnownPositionRef.current}
              onClose={() => setShowMap(false)}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default App;
