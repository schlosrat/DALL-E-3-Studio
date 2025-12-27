import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import threading
import requests
from io import BytesIO
from PIL import Image, ImageTk
from openai import OpenAI

class DalleApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DALL-E 3 Studio")
        self.root.geometry("1150x900")

        self.history = []
        self.current_img_data = None
        self.quality_var = tk.StringVar(value="standard")
        self.size_var = tk.StringVar(value="1024x1024")
        
        # New variables for Seed and Style
        self.seed_var = tk.StringVar(value="")
        self.use_seed_var = tk.BooleanVar(value=False)
        self.style_var = tk.StringVar(value="")

        self.paned = tk.PanedWindow(root, orient="horizontal", sashwidth=4)
        self.paned.pack(fill="both", expand=True)

        # LEFT SIDE: Controls
        left_frame = tk.Frame(self.paned, padx=20, pady=10)
        self.paned.add(left_frame, width=700)

        tk.Label(left_frame, text="OpenAI API Key:", font=("Arial", 10, "bold")).pack(anchor="w")
        self.api_entry = tk.Entry(left_frame, width=60, show="*")
        self.api_entry.pack(fill="x", pady=(0, 10))

        # --- SETTINGS PANES ---
        settings_container = tk.Frame(left_frame)
        settings_container.pack(fill="x", pady=5)

        size_pane = tk.LabelFrame(settings_container, text="Quality", padx=10, pady=10)
        size_pane.pack(side="left", fill="both", expand=True, padx=(0, 5))
        ttk.Radiobutton(size_pane, text="Standard", variable=self.quality_var, value="standard").pack(side="left", padx=5)
        ttk.Radiobutton(size_pane, text="HD", variable=self.quality_var, value="hd").pack(side="left", padx=5)

        aspect_pane = tk.LabelFrame(settings_container, text="Aspect Ratio", padx=10, pady=10)
        aspect_pane.pack(side="left", fill="both", expand=True, padx=(5, 0))
        ttk.Radiobutton(aspect_pane, text="Square", variable=self.size_var, value="1024x1024").pack(side="left", padx=5)
        ttk.Radiobutton(aspect_pane, text="Portrait", variable=self.size_var, value="1024x1792").pack(side="left", padx=5)
        ttk.Radiobutton(aspect_pane, text="Landscape", variable=self.size_var, value="1792x1024").pack(side="left", padx=5)

        # --- NEW: ARTISTIC CONTROLS (Style and Seed) ---
        art_pane = tk.LabelFrame(left_frame, text="Artistic Controls", padx=10, pady=10)
        art_pane.pack(fill="x", pady=10)

        tk.Label(art_pane, text="In The Style Of:").grid(row=0, column=0, sticky="w")
        self.style_entry = tk.Entry(art_pane, textvariable=self.style_var)
        self.style_entry.grid(row=0, column=1, columnspan=2, sticky="ew", padx=5)

        tk.Label(art_pane, text="Seed:").grid(row=1, column=0, sticky="w", pady=(5, 0))
        # Validation for integer only
        vcmd = (self.root.register(self.validate_seed), '%P')
        self.seed_entry = tk.Entry(art_pane, textvariable=self.seed_var, validate="key", validatecommand=vcmd)
        self.seed_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=(5, 0))
        
        self.seed_check = tk.Checkbutton(art_pane, text="Use Seed", variable=self.use_seed_var)
        self.seed_check.grid(row=1, column=2, padx=5, pady=(5, 0))
        
        art_pane.columnconfigure(1, weight=1)

        tk.Label(left_frame, text="Prompt:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(10, 0))
        self.prompt_text = tk.Text(left_frame, height=4)
        self.prompt_text.pack(fill="x", pady=5)

        btn_frame = tk.Frame(left_frame)
        btn_frame.pack(fill="x")
        self.gen_button = tk.Button(btn_frame, text="Generate", command=self.on_generate_click, bg="#28a745", fg="white", width=15)
        self.gen_button.pack(side="left", padx=5)
        self.save_button = tk.Button(btn_frame, text="Save Current", command=self.save_image, bg="#007BFF", fg="white", width=15, state="disabled")
        self.save_button.pack(side="left", padx=5)

        self.progress = ttk.Progressbar(left_frame, mode="indeterminate")
        self.progress.pack(fill="x", pady=10)

        self.image_display = tk.Label(left_frame, bg="#333333", height=30)
        self.image_display.pack(fill="both", expand=True)

        # RIGHT SIDE: History
        right_frame = tk.Frame(self.paned, padx=10, pady=10, bg="#f8f9fa")
        self.paned.add(right_frame, width=400)

        tk.Label(right_frame, text="Session History", font=("Arial", 12, "bold"), bg="#f8f9fa").pack()
        self.history_listbox = tk.Listbox(right_frame, font=("Arial", 9))
        self.history_listbox.pack(fill="both", expand=True, pady=5)
        self.history_listbox.bind("<<ListboxSelect>>", self.on_history_select)

        self.clear_button = tk.Button(right_frame, text="Clear History", command=self.clear_history, bg="#dc3545", fg="white")
        self.clear_button.pack(fill="x", pady=5)

    def validate_seed(self, P):
        if P == "" or P.isdigit():
            return True
        return False

    def on_generate_click(self):
        api_key = self.api_entry.get().strip()
        user_prompt = self.prompt_text.get("1.0", tk.END).strip()
        style_prefix = self.style_var.get().strip()
        
        if not api_key or not user_prompt: return

        # Construct prompt with style prefix if available
        full_prompt = f"{style_prefix} {user_prompt}".strip() if style_prefix else user_prompt

        self.gen_button.config(state="disabled")
        self.progress.start(10)
        
        # Determine if we pass a seed parameter
        seed_to_use = None
        if self.use_seed_var.get() and self.seed_var.get().isdigit():
            seed_to_use = int(self.seed_var.get())

        threading.Thread(target=self.generate_image, args=(api_key, full_prompt, seed_to_use)).start()

    def generate_image(self, api_key, prompt, seed):
        try:
            client = OpenAI(api_key=api_key)
            
            # API Call Parameters
            params = {
                "model": "dall-e-3",
                "prompt": prompt,
                "size": self.size_var.get(),
                "quality": self.quality_var.get(),
                "n": 1
            }
            if seed is not None:
                params["seed"] = seed

            response = client.images.generate(**params)
            
            # Retrieve the revised prompt and seed from the DALL-E response
            final_seed = response.data[0].seed
            raw_data = requests.get(response.data[0].url).content
            
            img = Image.open(BytesIO(raw_data))
            img.thumbnail((650, 500), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)

            new_entry = {
                "prompt": prompt, 
                "photo": photo, 
                "raw": raw_data, 
                "seed": final_seed
            }
            self.history.insert(0, new_entry)
            self.root.after(0, self.update_ui_with_new, new_entry)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.root.after(0, self.progress.stop)
            self.root.after(0, lambda: self.gen_button.config(state="normal"))

    def update_ui_with_new(self, entry):
        self.progress.stop()
        self.gen_button.config(state="normal")
        self.save_button.config(state="normal")
        
        # Update the seed field with the returned seed from DALL-E
        if not self.use_seed_var.get():
            self.seed_var.set(str(entry["seed"]))
            
        self.history_listbox.insert(0, f"[{len(self.history)}] {entry['prompt'][:35]}...")
        self.display_entry(entry)

    def on_history_select(self, event):
        selection = self.history_listbox.curselection()
        if selection:
            self.display_entry(self.history[selection[0]])

    def display_entry(self, entry):
        self.image_display.config(image=entry["photo"])
        self.image_display.image = entry["photo"]
        self.current_img_data = entry["raw"]
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", entry["prompt"])
        # Display the seed associated with this historical image
        if not self.use_seed_var.get():
            self.seed_var.set(str(entry.get("seed", "")))

    def clear_history(self):
        if messagebox.askyesno("Clear History", "Delete all generated images in this session?"):
            self.history.clear()
            self.history_listbox.delete(0, tk.END)
            self.image_display.config(image="", text="History Cleared")
            self.image_display.image = None
            self.save_button.config(state="disabled")
            self.prompt_text.delete("1.0", tk.END)
            if not self.use_seed_var.get():
                self.seed_var.set("")

    def save_image(self):
        if not self.current_img_data: return
        path = filedialog.asksaveasfilename(defaultextension=".png")
        if path:
            with open(path, "wb") as f: f.write(self.current_img_data)

if __name__ == "__main__":
    root = tk.Tk()
    app = DalleApp(root)
    root.mainloop()