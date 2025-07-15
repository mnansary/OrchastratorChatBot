# app_ocr.py

import gradio as gr
from core.imageanalyzer import ImageAnalyzer
import time

# Initialize the analyzer once when the app starts
try:
    analyzer = ImageAnalyzer()
except ValueError as e:
    # If the analyzer fails to initialize (e.g., missing API key),
    # we'll display an error and disable the interface.
    print(f"❌ FATAL: {e}")
    analyzer = None

def get_ocr_or_answer(image_path, question):
    """
    The main function that Gradio will call. It handles the logic
    of passing the inputs to the ImageAnalyzer.
    """
    if analyzer is None:
        yield "ERROR: Application is not configured correctly. Please check server logs for details."
        return

    if image_path is None:
        yield "Please upload an image to analyze."
        return

    # Gradio now provides the image path directly, which is what we need.
    print(f"--- Received image path: {image_path} ---") # Debug print
    
    # The analyzer returns a generator, so we stream the output.
    output_text = ""
    generator = analyzer.analyze_image(image_path, question)
    
    for chunk in generator:
        output_text += chunk
        yield output_text
        time.sleep(0.01) # Small delay for a smoother streaming effect in UI

# --- Gradio Interface Definition ---
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        """
        # Multimodal OCR and Q&A
        Upload an image to perform OCR. You can also provide an optional question to ask about the image content.
        Powered by the model specified in your configuration.
        """
    )
    
    with gr.Row():
        with gr.Column(scale=1):
            # =========== FIX APPLIED HERE ===========
            image_input = gr.Image(type="filepath", label="Upload Image")
            # ========================================
            
            prompt_input = gr.Textbox(
                label="Ask a specific question (Optional)",
                placeholder="e.g., What is the total amount on this receipt?"
            )
            submit_button = gr.Button("Analyze Image", variant="primary")

        with gr.Column(scale=2):
            output_display = gr.Textbox(
                label="Analysis Output", 
                interactive=False, 
                lines=15,
                placeholder="Output will appear here..."
            )
    
    # Connect the button click to the processing function
    submit_button.click(
        fn=get_ocr_or_answer,
        inputs=[image_input, prompt_input],
        outputs=output_display
    )
    
    # Add examples for users to try
    gr.Examples(
        examples=[
            ["./examples/receipt.png", "What is the grand total?"],
            ["./examples/document.png", ""],
            ["./examples/sign.jpg", "What are the hours of operation?"],
        ],
        inputs=[image_input, prompt_input]
    )
    
    # Create an 'examples' directory with some sample images for the examples to work.
    # For instance: ./examples/receipt.png, ./examples/document.png, etc.

# Disable the interface if the analyzer failed to load
if analyzer is None:
    demo.load(
        fn=lambda: gr.update(interactive=False),
        inputs=None,
        outputs=[image_input, prompt_input, submit_button]
    )

if __name__ == "__main__":
    demo.launch()