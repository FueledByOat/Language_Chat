print("Starting Up.  Get ready to record")

import audio_io
import audio_io.audio_io
import language_model
import language_model.language_model
import translation
import translation.translator
import translation.vosk_transcribe
import utils.helper
import time


def main():

    # prompt user for target language
    tl_selection = int(input("""Select Language:\n\
                     1 - Chinese\n\
                     2 - Japanese\n\
                     """))
    tl_main = "Chinese" if tl_selection == 1 else "Japanese"
    
    while True:
        # Step 0: Record Audio Sample
        # Step 1: Target Language Speech Recognition with Vosk

        # Try to capture and transcribe audio 3 times
        for i in range(3):
            try:
                audio_io.audio_io.listen()
                transcribed_text = translation.vosk_transcribe.transcribe(tl = tl_main)
            except:
                if i < 2:
                    print("Sorry, didn't catch that.  Let's try again")
                else: 
                    print("Looks like there's an issue hearing you.  Let's try again later")
                    time.sleep(2)
                    return
                i += 1
            else: 
                break

        # Step 2: Translate from Target Language to English 
        translated_text = translation.translator.translate_target_to_english(transcribed_text, language = tl_main)
        
        # Step 3: Generate a reply from the model
        bot_reply = language_model.language_model.bot_response(translated_text)

        # Step 4: Translate to Target Language
        bot_reply_in_tl = translation.translator.translate_english_to_target(bot_reply, language = tl_main)

        # Step 5: The computer speaks in TL
        audio_io.audio_io.speak(bot_reply_in_tl, language = tl_main)

        # Step 6: Options
        user_input = 2
        question = """Select one of the following options by typing the associate number:\n\
        1 - Continue Conversing\n\
        2 - Regenerate Bot Output\n\
        3 - Exit\n"""
        
        while user_input == 2:
            user_input = int(input(question))
            
            if user_input not in [1,2,3]:
                user_input = int(input(question))
            elif user_input == 3:
                utils.helper.cleanup()
                return
            elif user_input == 2:
                bot_reply = language_model.language_model.bot_response(translated_text)
                bot_reply_in_tl = translation.translator.translate_english_to_target(bot_reply, language = tl_main)
                audio_io.audio_io.speak(bot_reply_in_tl, language = tl_main)
    
if __name__ == "__main__":
    main()