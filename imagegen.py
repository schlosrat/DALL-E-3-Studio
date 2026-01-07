import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import openai
import threading
import requests
from PIL import Image, ImageTk
import io
import os

class Dalle3Studio:
    def __init__(self, root):
        self.root = root
        self.root.title("DALL-E 3 Studio")
        self.root.geometry("1100x1050") # Slightly larger to accommodate prompt display

        self.history = []
        self.current_image = None

        # Main Layout
        self.main_paned = tk.PanedWindow(root, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill="both", expand=True)

        self.left_frame = tk.Frame(self.main_paned, padx=10, pady=10)
        self.right_frame = tk.Frame(self.main_paned, padx=10, pady=10)

        self.main_paned.add(self.left_frame, stretch="always")
        self.main_paned.add(self.right_frame, width=350)

        self.create_left_widgets()
        self.create_right_widgets()

    def create_left_widgets(self):
        # API Key
        tk.Label(self.left_frame, text="OpenAI API Key:").pack(anchor="w")
        self.api_key_entry = tk.Entry(self.left_frame, show="*", width=50)
        self.api_key_entry.pack(fill="x", pady=(0, 10))

        # Quality and Aspect Ratio Frame
        options_frame = tk.Frame(self.left_frame)
        options_frame.pack(fill="x", pady=5)

        q_frame = tk.LabelFrame(options_frame, text="Quality", padx=5, pady=5)
        q_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self.quality_var = tk.StringVar(value="standard")
        tk.Radiobutton(q_frame, text="Standard", variable=self.quality_var, value="standard").pack(side="left")
        tk.Radiobutton(q_frame, text="HD", variable=self.quality_var, value="hd").pack(side="left")

        ar_frame = tk.LabelFrame(options_frame, text="Aspect Ratio", padx=5, pady=5)
        ar_frame.pack(side="left", fill="both", expand=True)
        self.size_var = tk.StringVar(value="1024x1024")
        tk.Radiobutton(ar_frame, text="Square", variable=self.size_var, value="1024x1024").pack(side="left")
        tk.Radiobutton(ar_frame, text="Portrait", variable=self.size_var, value="1024x1792").pack(side="left")
        tk.Radiobutton(ar_frame, text="Landscape", variable=self.size_var, value="1792x1024").pack(side="left")

        # Prompt Panel
        prompt_panel = tk.LabelFrame(self.left_frame, text="Prompt Panel", padx=10, pady=10)
        prompt_panel.pack(fill="x", pady=10)

        tk.Label(prompt_panel, text="Artistic Style Block:").pack(anchor="w")
        self.style_input = scrolledtext.ScrolledText(prompt_panel, height=3, font=("Arial", 10))
        self.style_input.pack(fill="x", pady=(0, 5))
        self.style_input.insert("1.0", "dark fantasy digital painting style, rpg concept art, dramatic chiaroscuro lighting, deep shadows, rich painterly brushstrokes, gritty texture, serious and moody atmosphere, muted color palette,")

        tk.Label(prompt_panel, text="Subject Description:").pack(anchor="w")
        self.subject_input = scrolledtext.ScrolledText(prompt_panel, height=4, font=("Arial", 10))
        self.subject_input.pack(fill="x", pady=(0, 5))

        toggle_frame = tk.Frame(prompt_panel)
        toggle_frame.pack(anchor="w")
        tk.Label(toggle_frame, text="Style Placement:").pack(side="left")
        self.placement_var = tk.BooleanVar(value=True) 
        tk.Radiobutton(toggle_frame, text="Leading", variable=self.placement_var, value=True).pack(side="left", padx=5)
        tk.Radiobutton(toggle_frame, text="Trailing", variable=self.placement_var, value=False).pack(side="left")

        # Action Buttons
        btn_frame = tk.Frame(self.left_frame)
        btn_frame.pack(fill="x", pady=5)
        self.gen_btn = tk.Button(btn_frame, text="Generate", command=self.start_generation, bg="#4CAF50", fg="white", width=15)
        self.gen_btn.pack(side="left", padx=5)
        self.save_btn = tk.Button(btn_frame, text="Save Current", command=self.save_image, width=15)
        self.save_btn.pack(side="left")

        self.progress = ttk.Progressbar(self.left_frame, mode='indeterminate')
        self.progress.pack(fill="x", pady=5)

        # Image Display
        self.image_label = tk.Label(self.left_frame, text="Image Preview", bg="#f0f0f0", height=15)
        self.image_label.pack(fill="both", expand=True)

        # --- RESTORED: FULL PROMPT DISPLAY ---
        tk.Label(self.left_frame, text="Full Combined Prompt Used:", font=("Arial", 9, "bold")).pack(anchor="w", pady=(10, 0))
        self.full_prompt_display = scrolledtext.ScrolledText(self.left_frame, height=3, font=("Consolas", 9), bg="#f8f8f8", state="disabled")
        self.full_prompt_display.pack(fill="x", pady=5)

    def create_right_widgets(self):
        tk.Label(self.right_frame, text="Session History", font=("Arial", 12, "bold")).pack(pady=5)
        tk.Label(self.right_frame, text="(Shows Subject Description only)", font=("Arial", 8, "italic"), fg="gray").pack()
        self.history_list = tk.Listbox(self.right_frame, font=("Arial", 10))
        self.history_list.pack(fill="both", expand=True, pady=5)
        self.history_list.bind('<<ListboxSelect>>', self.load_history_item)
        tk.Button(self.right_frame, text="Clear History", command=self.clear_history).pack(fill="x", pady=5)

    def get_combined_prompt(self):
        style = self.style_input.get("1.0", tk.END).strip()
        subject = self.subject_input.get("1.0", tk.END).strip()
        if not style: return subject
        if not subject: return style
        return f"{style}, {subject}" if self.placement_var.get() else f"{subject}, {style}"

    def start_generation(self):
        api_key = self.api_key_entry.get().strip()
        if not api_key:
            messagebox.showerror("Error", "Missing API Key")
            return
        
        # Capture current inputs to store in history
        style = self.style_input.get("1.0", tk.END).strip()
        subject = self.subject_input.get("1.0", tk.END).strip()
        placement = self.placement_var.get()
        full_prompt = self.get_combined_prompt()

        if not subject:
            messagebox.showwarning("Warning", "Subject cannot be empty")
            return

        self.gen_btn.config(state="disabled")
        self.progress.start()
        threading.Thread(target=self.run_generation, args=(api_key, full_prompt, style, subject, placement)).start()

    def run_generation(self, api_key, full_prompt, style, subject, placement):
        try:
            client = openai.OpenAI(api_key=api_key)
            response = client.images.generate(
                model="dall-e-3", prompt=full_prompt, size=self.size_var.get(), quality=self.quality_var.get(), n=1
            )
            image_url = response.data[0].url
            img_data = requests.get(image_url).content
            img = Image.open(io.BytesIO(img_data))
            
            self.root.after(0, self.update_ui_with_image, img, full_prompt, style, subject, placement)
        except Exception as e:
            # self.root.after(0, lambda: messagebox.showerror("API Error", str(e)))
            # Adding 'e=e' captures the exception object immediately
            self.root.after(0, lambda e=e: messagebox.showerror("API Error", str(e)))
        finally:
            self.root.after(0, self.stop_progress)

    def update_ui_with_image(self, img, full_prompt, style, subject, placement):
        self.current_image = img
        display_img = img.copy()
        display_img.thumbnail((512, 512))
        photo = ImageTk.PhotoImage(display_img)
        self.image_label.config(image=photo, text="")
        self.image_label.image = photo
        
        # Update full prompt display
        self.full_prompt_display.config(state="normal")
        self.full_prompt_display.delete("1.0", tk.END)
        self.full_prompt_display.insert("1.0", full_prompt)
        self.full_prompt_display.config(state="disabled")

        # Update history storage with individual components
        self.history.append({
            "style": style, 
            "subject": subject, 
            "placement": placement, 
            "full_prompt": full_prompt, 
            "image": img
        })
        # History list exclusively shows the subject
        self.history_list.insert(0, subject[:60].replace("\n", " ") + "...")

    def stop_progress(self):
        self.progress.stop()
        self.gen_btn.config(state="normal")

    def load_history_item(self, event):
        selection = self.history_list.curselection()
        if selection:
            # Calculate index based on reverse insertion
            index = len(self.history) - 1 - selection[0]
            item = self.history[index]
            
            # 1. Update Image
            self.current_image = item["image"]
            display_img = self.current_image.copy()
            display_img.thumbnail((500, 500))
            photo = ImageTk.PhotoImage(display_img)
            self.image_label.config(image=photo)
            self.image_label.image = photo

            # 2. Restore Inputs
            self.style_input.delete("1.0", tk.END)
            self.style_input.insert("1.0", item["style"])
            
            self.subject_input.delete("1.0", tk.END)
            self.subject_input.insert("1.0", item["subject"])
            
            self.placement_var.set(item["placement"])

            # 3. Restore Full Prompt Display
            self.full_prompt_display.config(state="normal")
            self.full_prompt_display.delete("1.0", tk.END)
            self.full_prompt_display.insert("1.0", item["full_prompt"])
            self.full_prompt_display.config(state="disabled")

    def save_image(self):
        if self.current_image:
            file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")])
            if file_path:
                self.current_image.save(file_path)

    def clear_history(self):
        self.history = []
        self.history_list.delete(0, tk.END)
        self.image_label.config(image="", text="History cleared")

if __name__ == "__main__":
    root = tk.Tk()
    app = Dalle3Studio(root)
    root.mainloop()