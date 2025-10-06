# This is a Gradio app titled "AI Client" designed to provide responses to user(therapist) messages.
import gradio as gr
import os
from groq import Groq

client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)

# Define a function that generates a response based on the user's message and chat history.
def client_response(message, history):

    chat_completion = client.chat.completions.create(
    messages=[
        {
            "role": "system",
            "content": "You are Jitesh, a 19 year old RESERVED male client who just broke up with his girlfriend and is feeling sad and lonely. Do not break the character and be hesitant to respond to the therapist's messages, and do not respond in more than 1 line. Example- '[Looks down] I am not feeling well.' DO NOT share all the information about the character, just respond naturally as the character.",
        },
        {
                "role": "user", 
                "content": message
            }
    ],
    model="llama-3.3-70b-versatile",
)

    return (chat_completion.choices[0].message.content)

# Create a Gradio ChatInterface that uses the therapeutic_response function.
demo = gr.ChatInterface(client_response, type="messages", autofocus=False, title="Jitesh: A client in need of therapy.")

# Launch the interface.
if __name__ == "__main__":
    demo.queue().launch(inbrowser=False, show_error=True, share=True)



