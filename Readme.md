<p align="center">
  <img src="aiva.png" alt="AIVA Logo" width="300" height="300">
</p>

<h1 align="center">AIVA - Artificial Intelligence Visual Assistant</h1>
An AI-powered visual assistance platform that empowers everyone through real-time scene understanding, voice interaction, and intelligent image capture.

<h4> AIVA brings the power of Google's Gemini 2.0 multimodal AI to create an accessible, real-time visual assistant. Whether you're visually impaired, need hands-free assistance, or simply want an AI companion to understand your surroundings, this app makes the world more accessible. </h4>

<p align="center">
  <a href="https://aiva-988633298112.us-west1.run.app/">
    <img src="https://img.shields.io/badge/🚀%20Try%20It%20Live-Click%20Here-brightgreen?style=for-the-badge" alt="Try Live Demo"/>
  </a>
  <a href="https://www.youtube.com/watch?v=sNPtSqpnk0Y">
    <img src="https://img.shields.io/badge/%20Watch%20Demo-YouTube-red?style=for-the-badge&logo=youtube" alt="Watch Demo"/>
  </a>
</p>

## ✨ Features

### 🎥 **Live Camera Support**
- Front and rear camera switching.
- Real-time video streaming to AI and voice chat!

### 🎤 **Real Time Voice Responses**
- Natural conversation with AI about your surroundings.
- Real-time scene description and object recognition.
- Hands-free operation perfect for accessibility.

### 📸 **Smart Image Capture**
- Voice-commanded photo capture.
- Automatic saving with intelligent naming.

### 📧 **Intelligent Email Integration**
- Email captured images with voice commands.
- "Email this abcd@example.com" - automatic recipient detection and sends image as attatchement!

### 🔒 **Privacy-First Design**
- Secure WebSocket communication
- No data retention beyond session

---

## 🎯 Social Impact & Hackathon Vision

AIVA was created to address the **Accessibility** theme of the USC Viterbi AI/ML for Social Good Hackathon. My mission is to leverage modern AI to empower the visually impaired community and demonstrate that inclusive, ethical technology can be accessible to everyone.

### Why This Matters

According to the World Health Organization, over 2.2 billion people worldwide have vision impairment. Many existing assistive technologies are expensive, require specialized training, or aren't available in all languages. **AIVA changes this.**

### Impact on Visually Challenged Individuals

This app is **transformative** for people with visual impairments because it:

- **Requires zero training** - just speak naturally
- **Works on any smartphone** - no expensive hardware needed
- **Provides instant scene understanding** - know what's around you
- **Reads text aloud** - access printed information independently
- **Captures and emails information** - save important details for later
- **Offers real-time assistance** - get help navigating unfamiliar spaces/objects/machines...etc

### Universal Design for All

While designed with visual impairment in mind, AIVA Companion serves everyone:
- Elderly users who need reading assistance
- Students documenting lectures or whiteboards
- Travelers navigating foreign languages
- Anyone needing hands-free visual assistance

## Step-by-Step Screenshots

### Step 1: Open the app (Web View)
![Step 1](https://drive.google.com/thumbnail?id=1wPjzDxW8ERBjfv8HMdhBrA_twX2a1q9_&sz=w600)

### Mobile View
![Step 2](https://drive.google.com/thumbnail?id=1jNW07sqHJA7J3gBVOmvEh5WPQV_mij-k&sz=w600)

### Step 2: Select either front or rear camera
![Step 3](https://drive.google.com/thumbnail?id=1BrviZga0DtBXTo-LncOu79Z045SyyEKh&sz=w600)

### Step 3: Select Start AIVA
![Step 3](https://drive.google.com/thumbnail?id=1eZMkmOQGq5ZmK9jJG7V6c51scTFgBxXZ&sz=w600)

### Step 4: Start talking!
![Step 4](https://drive.google.com/thumbnail?id=1clif3rHJE_N7n9ExIYFtngBOAWAUkyR_&sz=w600)


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

# for email functionality (optional)
cd backend
- Activate GMAIL API for your account, read up the docs and add your credentials.json and token.json files in here

# Build and run

docker build -t aiva .
docker run -p 8080:8080 -e GOOGLE_API_KEY=<your_api_key_here> aiva

```

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
"What did I keep my earphones?"
"Show session summary"
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

## Thank You!
AIVA is **just the beginning**: a glimpse into how AI can truly see and understand the world around us.  

With its foundation in real-time vision, voice interaction, and intelligent automation, AIVA has immense potential to evolve into a full-fledged personal assistant that makes everyday life simpler, smarter, and more connected.

Future updates could bring object tracking, smart home integration, and wearable device support, transforming AIVA into an always-available visual companion that bridges technology and human experience.

✨ AIVA isn’t just an app; it’s the next step toward a more accessible, high-tech world where AI helps everyone see, understand, and interact effortlessly.