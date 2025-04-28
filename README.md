# Language Learning Web App

This project is a web-based language tool that currently has two modes, conversation through text and chat, as well as an image guessing game to identify items within a random image. 
**Facilitates real-time transcription, translation, and dialogue generation for **Chinese** and **Japanese**. It uses **Vosk** for speech recognition, **Hugging Face transformers** for natural language processing, and **DialoGPT** for conversational AI.

## 📌 Features  
### Conversation Mode 
- **Speech Recognition**: Converts spoken Chinese and Japanese into text using **Vosk**  
- **Machine Translation**: Translates recognized speech into English  
- **Conversational AI**: Generates context-aware responses with **DialoGPT**  
- **Text-to-Speech (TTS)**: Outputs responses in the original language  
- **Web-Based Interface**: Built using **Python and JavaScript** for interactive usage

### Image Game Mode 
- **Speech Recognition**: Converts spoken Chinese and Japanese into text using **Vosk**
- **Zero Shot Object Detection**: Identifies supplied text within a random image using **google/owlv2-base-patch16-ensemble**

## 🛠️ Setup Instructions  
### **1. Clone the Repository**  
```sh  
git clone https://github.com/yourusername/your-repo.git  
cd your-repo  
```

### **2. Create a Virtual Environment and Install Dependencies**  
```sh  
python -m venv venv  
source venv/bin/activate  # macOS/Linux  
venv\Scripts\activate  # Windows  

pip install -r requirements.txt  
```

### **3. Run the Application**  
```sh  
python app.py  
```

## 🗄️ Project Structure  
```
├── app.py             # Main application script
├── static/            # JavaScript and CSS files
├── templates/         # HTML templates for the UI
├── translation/       # Pre-trained language models and custom functions
├── audio_io/          # Processes user input and output
├── requirements.txt   # Dependencies
└── README.md          # Project documentation
```

## 🚀 Planned Features  
- Improve AI-generated responses using fine-tuned **DialoGPT** or a different language model
- Enhance UI with real-time speech visualization of Pinyin

## 🤝 Contributing  
1. Fork the repo  
2. Create a new branch (`git checkout -b feature/new-feature`)  
3. Commit your changes (`git commit -m "Added new feature"`)  
4. Push the branch (`git push origin feature/new-feature`)  
5. Open a Pull Request  

## 📜 License  
This project is licensed under the MIT License.
