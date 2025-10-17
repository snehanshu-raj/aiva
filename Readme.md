<p align="center">
  <img src="aiva.png" alt="AIVA Logo" width="250" height="250">
</p>

<h1 align="center">AIVA - Artificial Intelligence Visual Assistant</h1>
An AI-powered visual assistance platform that empowers everyone through real-time scene understanding, voice interaction, and intelligent image capture.

<h4> AIVA brings the power of Google's Gemini 2.0 multimodal AI to create an accessible, real-time visual assistant. Whether you're visually impaired, need hands-free assistance, or simply want an AI companion to understand your surroundings, this app makes the world more accessible. </h4>

<p align="center">
  <a href="https://your-app-url.run.app">
    <img src="https://img.shields.io/badge/🚀%20Try%20It%20Live-Click%20Here-brightgreen?style=for-the-badge" alt="Try Live Demo"/>
  </a>
  <a href="https://www.youtube.com/watch?v=your-demo-video-id">
    <img src="https://img.shields.io/badge/%20Watch%20Demo-YouTube-red?style=for-the-badge&logo=youtube" alt="Watch Demo"/>
  </a>
</p>

## ✨ Features

### 🎤 **Voice-First Interaction**
- Natural conversation with AI about your surroundings.
- Real-time scene description and object recognition.
- Hands-free operation perfect for accessibility.

### 📸 **Smart Image Capture**
- Voice-commanded photo capture.
- Automatic saving with intelligent naming.
- Session-based organization with metadata.

### 📧 **Intelligent Email Integration**
- Email captured images with voice commands.
- "Email this to me" - automatic recipient detection.
- Attach specific captures to emails.

### 🎥 **Live Camera Support**
- Front and rear camera switching.
- Real-time video streaming to AI.
- Mobile-optimized camera controls.

### 🔒 **Privacy-First Design**
- Secure WebSocket communication
- No data retention beyond session

---

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker (optional)
- Google Gemini API key ([Get one here](https://ai.google.dev/))
- Gmail API credentials ([Setup guide](https://developers.google.com/gmail/api/quickstart/python))

### Installation

#### Option 1: Docker (Recommended)

```
# Clone the repository

git clone https://github.com/snehanshu-raj/aiva.git
cd aiva

# Create .env file

cat > backend/.env << EOF
GOOGLE_API_KEY=your-gemini-api-key
DEFAULT_EMAIL=your-email@gmail.com
SENDER_EMAIL=your-email@gmail.com
EOF

# Build and run

docker build -t vision-ai-companion .
docker run -p 8080:8080 --env-file backend/.env vision-ai-companion

```

#### Option 2: Manual Setup

```


# Clone repository

git clone https://github.com/yourusername/vision-ai-companion.git
cd vision-ai-companion

# Backend setup

cd backend
pip install -r requirements.txt
export GOOGLE_API_KEY="your-api-key"
export DEFAULT_EMAIL="your-email@gmail.com"
python main.py \&

# Frontend setup (new terminal)

cd frontend
npm install
npm start

```

### Access the App

- **Local**: http://localhost:8080
- **Mobile**: http://your-computer-ip:8080

---

## 📁 Project Structure

```

aiva/
├── backend/                   # FastAPI backend
│   ├── main.py                # Main application \& WebSocket handler
│   ├── requirements.txt       # Python dependencies
│   ├── credentials.json       # Gmail API credentials (not in repo)
│   ├── token.json             # Gmail auth token (generated)
│   └── captures/              # Saved images directory
│       └── metadata.json      # Image metadata storage
│
├── frontend/                  # React frontend
│   ├── src/
│   │   ├── App.js             # Main React component
│   │   └── App.css            # Styles
│   ├── public/                # Static assets
│   └── package.json           # Node dependencies
│
├── Dockerfile                 # Multi-stage Docker build
├── .dockerignore              # Docker ignore patterns
├── .env.example               # Environment variables template
└── README.md                  # This file

```

---

## 🎯 Use Cases

### For Visually Impaired Users
- **Scene Description**: "What's in front of me?"
- **Text Reading**: "Read the text on this sign"
- **Object Identification**: "What color is this shirt?"
- **Navigation Help**: "Describe my surroundings"

### For General Use
- **Help**: "How to operate this machine"
- **Documentation**: "Capture this whiteboard and email it to me"
- **Shopping**: "What product is this and what does it say?"
- **Cooking**: "Read me this recipe step by step"
- **Translation**: "What does this sign say in English?"

---

## 🗣️ Voice Commands

### Capture Commands
```
"Capture this as my desk"
"Take a picture of this scene"
"Save this as front door"

```

### Email Commands
```
"Email this to me"
"Send the desk picture to me"
"Email the front door image with subject 'Entry way'"

```

### Info & Search Commands
```
"Where did I see dogs first?"
"What did I capture?"
"Show me my pictures"
"List all captures"

```

### Session Commands
```

"What did I save today?"
"Show session summary"
"I am done, thank you"

```

---

## 🛠️ Technology Stack

### Backend
- **FastAPI** - Modern async web framework
- **Google Gemini 2.0** - Multimodal AI (vision + voice)
- **WebSockets** - Real-time bidirectional communication
- **Gmail API** - Email integration
- **Python 3.12** - Core language

### Frontend
- **React 18** - UI library
- **WebRTC** - Camera/microphone access
- **Canvas API** - Image processing
- **Web Audio API** - Audio streaming
- **CSS3** - Modern responsive design

### Infrastructure
- **Docker** - Containerization
- **Google Cloud Run** - Serverless deployment
- **Uvicorn** - ASGI server

---
