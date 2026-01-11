import sys
import os
import json
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QComboBox, QFileDialog, QMessageBox, QHBoxLayout, QVBoxLayout, 
    QProgressBar, QMainWindow, QDialog, QListWidget, QDialogButtonBox
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


def get_playlist_info(url):
    """Extract playlist or single video information"""
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'force_generic_extractor': False
    }
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if 'entries' in info:
                videos = []
                for entry in info['entries']:
                    if entry:
                        videos.append({
                            'url': f"https://www.youtube.com/watch?v={entry['id']}",
                            'title': entry.get('title', 'Unknown'),
                            'id': entry.get('id', '')
                        })
                
                return {
                    'is_playlist': True,
                    'title': info.get('title', 'Unknown Playlist'),
                    'count': len(videos),
                    'videos': videos
                }
            else:
                return {
                    'is_playlist': False,
                    'title': info.get('title', 'Unknown'),
                    'count': 1,
                    'videos': [{'url': url, 'title': info.get('title', 'Unknown'), 'id': info.get('id', '')}]
                }
    except Exception as e:
        raise Exception(f"Failed to extract video info: {str(e)}")


class PlaylistDialog(QDialog):
    """Dialog for selecting videos from a playlist"""
    def __init__(self, playlist_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Playlist: {playlist_info['title']}")
        self.playlist_info = playlist_info
        
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.MultiSelection)
        
        for video in playlist_info['videos']:
            self.list_widget.addItem(video['title'])
            
        self.list_widget.selectAll()
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.list_widget.selectAll)
        
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self.list_widget.clearSelection)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(deselect_all_btn)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f"{playlist_info['count']} videos found. Select videos to download:"))
        layout.addWidget(self.list_widget)
        layout.addLayout(button_layout)
        layout.addWidget(buttons)
        self.setLayout(layout)
        
        self.resize(500, 400)
    
    def get_selected_videos(self):
        """Return list of selected video dicts"""
        selected_indices = [item.row() for item in self.list_widget.selectedIndexes()]
        return [self.playlist_info['videos'][i] for i in selected_indices]


class DownloadWorker(QThread):
    finished = Signal(bool, str)
    progress = Signal(int, int)
    video_progress = Signal(int) 
    
    def __init__(self, videos, fmt, folder):
        super().__init__()
        self.videos = videos
        self.fmt = fmt
        self.folder = folder
        self.current_video = 0

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)
            if total:
                percent = int(downloaded / total * 100)
                self.video_progress.emit(percent)
        elif d['status'] == 'finished':
            self.video_progress.emit(100)

    def download_single(self, url):
        """Download a single video with original FFmpeg settings"""
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
        elif self.fmt == "FLAC (Lossless)":
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': outtmpl,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'flac',
                    'preferredquality': '320',
                }],
                'progress_hooks': [self.progress_hook],
                'quiet': True,
            }
        
        elif self.fmt == "MP4":
            ydl_opts = {
                'format': 'bv*[vcodec^=avc1]+ba[acodec^=mp4a]/b[ext=mp4]',
                'outtmpl': outtmpl,
                'merge_output_format': 'mp4',
                'progress_hooks': [self.progress_hook],
                'quiet': True,
            }

        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    def run(self):
        total = len(self.videos)
        failed = []
        
        for idx, video in enumerate(self.videos, 1):
            self.current_video = idx
            self.progress.emit(idx, total)
            
            try:
                self.download_single(video['url'])
            except Exception as e:
                failed.append(f"{video['title']}: {str(e)}")
        
        if failed:
            msg = f"Completed with {len(failed)} error(s):\n" + "\n".join(failed[:5])
            if len(failed) > 5:
                msg += f"\n... and {len(failed) - 5} more errors"
            self.finished.emit(False, msg)
        else:
            self.finished.emit(True, f"Downloaded {total} video(s) successfully!")


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YT2MPEG")

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("YouTube URL (video or playlist)")

        self.folder_edit = QLineEdit()
        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.clicked.connect(self.choose_folder)

        self.format_box = QComboBox()
        self.format_box.addItems(["MP3", "FLAC (Lossless)", "MP4"])

        folder_layout = QHBoxLayout()
        folder_layout.addWidget(self.folder_edit)
        folder_layout.addWidget(self.browse_btn)

        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.start_download)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        
        self.status_label = QLabel("")
        self.status_label.setVisible(False)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("YouTube URL:"))
        layout.addWidget(self.url_edit)
        layout.addWidget(QLabel("Output folder:"))
        layout.addLayout(folder_layout)
        layout.addWidget(QLabel("Format:"))
        layout.addWidget(self.format_box)
        layout.addWidget(self.download_btn)
        layout.addWidget(self.status_label)
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
        
        self.download_btn.setEnabled(False)
        self.status_label.setText("Checking URL...")
        self.status_label.setVisible(True)
        
        try:
            playlist_info = get_playlist_info(url)
            
            if playlist_info['is_playlist']:
                dialog = PlaylistDialog(playlist_info, self)
                if dialog.exec() == QDialog.Accepted:
                    videos = dialog.get_selected_videos()
                    if not videos:
                        QMessageBox.warning(self, "Error", "No videos selected")
                        self.download_btn.setEnabled(True)
                        self.status_label.setVisible(False)
                        return
                else:
                    self.download_btn.setEnabled(True)
                    self.status_label.setVisible(False)
                    return
            else:
                videos = playlist_info['videos']
            
            self.download_btn.setVisible(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_label.setText("Starting download...")

            self.worker = DownloadWorker(videos, fmt, folder)
            self.worker.video_progress.connect(self.progress_bar.setValue)
            self.worker.progress.connect(self.on_progress)
            self.worker.finished.connect(self.on_finished)
            self.worker.start()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process URL:\n{str(e)}")
            self.download_btn.setEnabled(True)
            self.status_label.setVisible(False)
    
    def on_progress(self, current, total):
        if total > 1:
            self.status_label.setText(f"Downloading video {current} of {total}")
        else:
            self.status_label.setText("Downloading...")

    def on_finished(self, success, message):
        self.download_btn.setVisible(True)
        self.download_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)

        if success:
            QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.critical(self, "Error", message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    ico = QIcon("./src/FILE.ico")
    window.setWindowIcon(ico)
    window.resize(450, 280)
    window.show()
    sys.exit(app.exec_())
