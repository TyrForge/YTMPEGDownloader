import tkinter as tk
from tkinter import messagebox
from yt_dlp import YoutubeDL
import threading

def start_download():
    threading.Thread(target=download, daemon=True).start()


def download():
    url = url_entry.get().strip()
    format_choice = format_var.get()

    if not url:
        messagebox.showerror("Error", "Please enter a YouTube URL")
        return

    download_btn.config(state="disabled")

    if format_choice == "MP3":
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': '%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'quiet': True,
        }
    else:  
        ydl_opts = {
            'format': 'bv*[vcodec^=avc1]+ba[acodec^=mp4a]/b[ext=mp4]',
            'outtmpl': '%(title)s.%(ext)s',
            'merge_output_format': 'mp4',
            'quiet': True,
        }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        messagebox.showinfo("Success", f"{format_choice} download complete!")
    except Exception as e:
        messagebox.showerror("Error", f"Download failed:\n{e}")
    finally:
        download_btn.config(state="normal")


root = tk.Tk()
root.title("YouTube Downloader")

tk.Label(root, text="YouTube URL:").pack(pady=5)
url_entry = tk.Entry(root, width=55)
url_entry.pack(padx=10, pady=5)

format_var = tk.StringVar(value="MP3")
tk.Label(root, text="Format:").pack(pady=5)
tk.OptionMenu(root, format_var, "MP3", "MP4").pack()

download_btn = tk.Button(root, text="Download", command=start_download)
download_btn.pack(pady=12)

root.mainloop()


