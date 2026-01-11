import sys
import os
import json
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QComboBox, QFileDialog, QMessageBox, QHBoxLayout, QVBoxLayout, QProgressBar, QMainWindow
)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QIcon
from yt_dlp import YoutubeDL


APP_NAME = "YT2MPEG"
prefs_path = os.path.join(os.getenv('APPDATA') or os.path.expanduser("~"), APP_NAME)
prefs_file = os.path.join(prefs_path, "prefs.json")


def load_prefs():
    if os.path.exists(prefs_file):
        try:
            with open(prefs_file, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_prefs(prefs):
    os.makedirs(prefs_path, exist_ok=True)
    with open(prefs_file, "w") as f:
        json.dump(prefs, f, indent=2)



class DownloadWorker(QThread):
    finished = Signal(bool, str)
    progress = Signal(int)

    def __init__(self, url, fmt, folder):
        super().__init__()
        self.url = url
        self.fmt = fmt
        self.folder = folder

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)
            if total:
                percent = int(downloaded / total * 100)
                self.progress.emit(percent)

        elif d['status'] == 'finished':
            self.progress.emit(100)

    def run(self):
        outtmpl = os.path.join(self.folder, "%(title)s.%(ext)s")

        if self.fmt == "MP3":
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': outtmpl,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
                'progress_hooks': [self.progress_hook],
                'quiet': True,
            }
        else:
            ydl_opts = {
                'format': 'bv*[vcodec^=avc1]+ba[acodec^=mp4a]/b[ext=mp4]',
                'outtmpl': outtmpl,
                'merge_output_format': 'mp4',
                'progress_hooks': [self.progress_hook],
                'quiet': True,
            }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            self.finished.emit(True, "Download complete!")
        except Exception as e:
            self.finished.emit(False, str(e))


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YT2MPEG")

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("YouTube URL")

        self.folder_edit = QLineEdit()
        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.clicked.connect(self.choose_folder)

        self.format_box = QComboBox()
        self.format_box.addItems(["MP3", "MP4"])

        folder_layout = QHBoxLayout()
        folder_layout.addWidget(self.folder_edit)
        folder_layout.addWidget(self.browse_btn)

        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.start_download)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("YouTube URL:"))
        layout.addWidget(self.url_edit)
        layout.addWidget(QLabel("Output folder:"))
        layout.addLayout(folder_layout)
        layout.addWidget(QLabel("Format:"))
        layout.addWidget(self.format_box)
        layout.addWidget(self.download_btn)
        layout.addWidget(self.progress_bar)

        self.setLayout(layout)

        self.prefs = load_prefs()
        self.folder_edit.setText(self.prefs.get("last_output_folder", ""))

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.folder_edit.setText(folder)
            self.prefs["last_output_folder"] = folder
            save_prefs(self.prefs)

    def start_download(self):
        url = self.url_edit.text().strip()
        folder = self.folder_edit.text().strip()
        fmt = self.format_box.currentText()

        if not url or not folder:
            QMessageBox.warning(self, "Error", "Please enter URL and output folder")
            return

        self.download_btn.setVisible(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.worker = DownloadWorker(url, fmt, folder)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_finished(self, success, message):
        self.download_btn.setVisible(True)
        self.progress_bar.setVisible(False)

        if success:
            QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.critical(self, "Error", message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    ico = QIcon("./src/FILE.ico")
    window.setWindowIcon(ico)
    window.resize(450, 220)
    window.show()
    sys.exit(app.exec_())
