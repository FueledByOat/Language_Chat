# **Language Learning Web App**

This project is a web-based language tool, **now powered by FastAPI**, that provides conversation practice and an image-guessing game.  
It facilitates real-time transcription, translation, and dialogue generation for **Chinese** and **Japanese**. It uses **Whisper** for speech recognition, **Hugging Face transformers** for natural language processing, and a multilingual LLM for conversational AI.

## **📌 Features**

### **Conversation Mode**

* **Speech Recognition**: Converts spoken Chinese and Japanese into text using **Whisper**.  
* **Machine Translation**: Translates user and bot text into English for review.  
* **Conversational AI**: Generates context-aware responses with a **multilingual LLM**.  
* **Text-to-Speech (TTS)**: Outputs bot responses as playable audio.  
* **Web-Based Interface**: Built using **FastAPI, Python, and vanilla JavaScript** for an interactive, asynchronous experience.

### **Image Game Mode**

* **Speech Recognition**: Converts spoken Chinese and Japanese into text using **Whisper**.  
* **Zero-Shot Object Detection**: Identifies user's spoken guess within a random image using **google/owlv2-base-patch16-ensemble**.

## **🛠️ Setup Instructions**

### **1\. Clone the Repository**

git clone \[https://github.com/yourusername/your-repo.git\](https://github.com/yourusername/your-repo.git)  
cd your-repo

### **2\. Create a Virtual Environment and Install Dependencies**

python \-m venv venv  
source venv/bin/activate  \# macOS/Linux  
venv\\Scripts\\activate   \# Windows

pip install \-r requirements.txt

### **3\. Run the Application**

The application is now served using Uvicorn, which is started by the main script.  
python main.py

The app will be available at http://127.0.0.1:5170 (or as configured).

## **🗄️ Project Structure**

├── main.py             \# Main FastAPI application script  
├── static/             \# JavaScript and CSS files  
├── templates/          \# HTML templates for the UI  
├── translation/        \# Translation and transcription modules  
├── language\_model/     \# Conversational LLM module  
├── audio\_io/           \# Text-to-Speech (TTS) module  
├── utils/              \# Helper scripts  
├── config.py           \# Configuration variables  
├── requirements.txt    \# Dependencies  
└── README.md           \# Project documentation

### **⌨️ Technologies Used**

* Python  
* **FastAPI**  
* **Uvicorn**  
* JavaScript  
* HTML  
* Hugging Face Transformers  
* LLMs (Whisper, etc.)

## **🚀 Planned Features**

With the FastAPI migration complete, future efforts can focus on:

* **WebSocket Integration**: Upgrade the chat API from HTTP requests to WebSockets for true real-time, bi-directional conversation.  
* **Task Queues**: Move heavy, blocking tasks (like transcription and LLM generation) to a separate worker queue (e.g., Celery) to make the API even more responsive.  
* **VQA Model**: Replace the zero-shot detector in the image game with a true Visual Question Answering (VQA) model (like LLaVA) for a more interactive game.  
* **Conversation History**: Add user authentication and a database to store conversation history.

## **🤝 Contributing**

1. Fork the repo  
2. Create a new branch (git checkout \-b feature/new-feature)  
3. Commit your changes (git commit \-m "Added new feature")  
4. Push the branch (git push origin feature/new-feature)  
5. Open a Pull Request

## **📜 License**

This project is licensed under the MIT License.