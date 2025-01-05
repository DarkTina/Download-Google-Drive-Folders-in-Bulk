import os
import pickle
import requests
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from time import time
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

class DownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Google Drive Folder Downloader")
        self.root.geometry("500x400")
        self.root.configure(bg="gray")

        self.folder_links = []
        self.save_path = tk.StringVar()
        self.downloading = False
        self.file_list = []
        self.current_file = None
        self.downloaded_bytes = 0
        self.download_state_file = "download_state.pickle"
        self.file_exists_action = tk.StringVar(value="skip")  # Biến lưu trữ hành động khi file tồn tại

        # UI components
        link_frame = tk.Frame(root, bg="gray")
        link_frame.pack(pady=5)

        tk.Label(link_frame, text="Folder Link:", bg="gray", fg="white").pack(
            side=tk.LEFT, padx=5
        )
        self.link_entry = tk.Entry(link_frame, width=35)
        self.link_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(
            link_frame,
            text="Add Link",
            command=self.add_link,
            bg="orange",
            fg="black",
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            root,
            text="Load Links from TXT",
            command=self.load_links_from_txt,
            bg="orange",
            fg="black",
        ).pack(pady=5)

        save_frame = tk.Frame(root, bg="gray")
        save_frame.pack(pady=5)

        tk.Label(save_frame, text="Save Path:", bg="gray", fg="white").pack(
            side=tk.LEFT, padx=5
        )
        tk.Entry(save_frame, textvariable=self.save_path, width=35).pack(
            side=tk.LEFT, padx=5
        )
        tk.Button(
            save_frame,
            text="Save to",
            command=self.choose_save_path,
            bg="orange",
            fg="black",
        ).pack(side=tk.LEFT, padx=5)

        # Thêm tùy chọn xử lý file trùng
        file_exists_frame = tk.Frame(root, bg="gray")
        file_exists_frame.pack(pady=5)

        tk.Label(
            file_exists_frame, text="If file exists:", bg="gray", fg="white"
        ).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(
            file_exists_frame,
            text="Skip",
            variable=self.file_exists_action,
            value="skip",
            bg="gray",
            fg="black",
        ).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(
            file_exists_frame,
            text="Replace",
            variable=self.file_exists_action,
            value="replace",
            bg="gray",
            fg="black",
        ).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(
            file_exists_frame,
            text="Rename",
            variable=self.file_exists_action,
            value="rename",
            bg="gray",
            fg="black",
        ).pack(side=tk.LEFT, padx=5)

        button_frame = tk.Frame(root, bg="gray")
        button_frame.pack(pady=5)

        tk.Button(
            button_frame,
            text="Start",
            command=self.start_download,
            bg="orange",
            fg="black",
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            button_frame,
            text="Pause",
            command=self.pause_download,
            bg="orange",
            fg="black",
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            button_frame,
            text="Resume",
            command=self.resume_download,
            bg="orange",
            fg="black",
        ).pack(side=tk.LEFT, padx=5)

        self.status_label = tk.Label(
            root, text="Status: Waiting to start...", fg="blue", bg="gray"
        )
        self.status_label.pack(pady=5)

        self.service = self.initialize_drive_service()

        self.restore_download_state()

    def initialize_drive_service(self):
        creds = Credentials.from_service_account_file(
            "credentials.json", scopes=["https://www.googleapis.com/auth/drive"]
        )
        service = build("drive", "v3", credentials=creds)
        return service

    def choose_save_path(self):
        path = filedialog.askdirectory()
        if path:
            self.save_path.set(path)

    def add_link(self):
        link = self.link_entry.get().strip()
        if link:
            self.folder_links.append(link)
            self.link_entry.delete(0, tk.END)
            messagebox.showinfo("Info", "Link added successfully!")
        else:
            messagebox.showerror("Error", "Please enter a valid link.")

    def load_links_from_txt(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if file_path:
            try:
                with open(file_path, "r") as file:
                    links = file.readlines()
                    self.folder_links.extend(link.strip() for link in links if link.strip())
                messagebox.showinfo("Info", f"Successfully loaded {len(links)} links from file.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load links: {e}")

    def start_download(self):
        if not self.folder_links or not self.save_path.get():
            messagebox.showerror("Error", "Please provide folder links and a save path!")
            return

        self.status_label.config(text="Fetching file lists...", fg="green")
        self.downloading = True

        threading.Thread(target=self.process_links).start()

    def process_links(self):
        try:
            for folder_link in self.folder_links:
                if not self.downloading:
                    break

                folder_id = self.extract_folder_id(folder_link)
                if not folder_id:
                    messagebox.showerror("Error", f"Invalid folder link: {folder_link}")
                    continue

                folder_name = self.get_folder_name(folder_id)
                if not folder_name:
                    messagebox.showerror("Error", f"Failed to fetch folder name for: {folder_link}")
                    continue

                target_path = os.path.join(self.save_path.get(), folder_name)
                os.makedirs(target_path, exist_ok=True)

                self.file_list = self.fetch_all_files(folder_id)
                if not self.file_list:
                    messagebox.showerror("Error", f"No files found in folder: {folder_link}")
                    continue

                self.status_label.config(text=f"Found {len(self.file_list)} files. Starting download...", fg="green")

                for i, file in enumerate(self.file_list):
                    if not self.downloading:
                        break
                    self.current_file = file
                    self.current_file["output_dir"] = target_path
                    self.current_file["index"] = i
                    self.download_file(file["id"], file["name"], target_path, file["path"])
                    # self.file_list.pop(i)  # Xóa file khỏi danh sách sau khi tải xong
                    self.save_download_state()

            self.status_label.config(text="Download completed!" if self.downloading else "Paused.", fg="blue")
            self.downloading = False
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            self.status_label.config(text="Error downloading files.", fg="red")

    def extract_folder_id(self, folder_link):
        try:
            if "folders" in folder_link:
                return folder_link.split("/folders/")[1].split("?")[0]
            return folder_link.split("/")[-1].split("?")[0]
        except IndexError:
            return None

    def get_folder_name(self, folder_id):
        try:
            folder = self.service.files().get(fileId=folder_id, fields="name").execute()
            return folder.get("name")
        except Exception as e:
            print(f"Error fetching folder name: {e}")
            return None

    def pause_download(self):
        self.downloading = False
        self.status_label.config(text="Download paused...", fg="orange")

    def resume_download(self):
        if not self.downloading:
            self.downloading = True
            self.status_label.config(text="Resuming download...", fg="green")
            self.downloaded_bytes = 0
            threading.Thread(target=self.process_download).start()

    def process_download(self):
        try:
            if self.current_file and "relative_path" in self.current_file:
                self.status_label.config(text=f"Continuing download {self.current_file['name']}...", fg="green")
                self.download_file(self.current_file["id"], self.current_file["name"], self.current_file["output_dir"], self.current_file["relative_path"])

            # Bắt đầu từ file tiếp theo sau khi resume
            for i in range(self.current_file["index"] + 1 if self.current_file else 0, len(self.file_list)):  
                if not self.downloading:
                    break
                file = self.file_list[i]
                self.current_file = file
                self.current_file["output_dir"] = os.path.join(self.save_path.get(), self.get_folder_name(self.extract_folder_id(self.folder_links[0])))
                self.current_file["index"] = i
                self.download_file(file["id"], file["name"], self.current_file["output_dir"], file["path"])
                # self.file_list.pop(i)  # Xóa file khỏi danh sách sau khi tải xong

            self.current_file = None
            self.status_label.config(text="Download completed!" if self.downloading else "Paused.", fg="blue")
            self.downloading = False
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            self.status_label.config(text="Error downloading files.", fg="red")

    def fetch_all_files(self, folder_id, current_path=""):
        try:
            all_files = []

            results = self.service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="files(id, name, mimeType)"
            ).execute()

            items = results.get("files", [])

            for item in items:
                if item["mimeType"] == "application/vnd.google-apps.folder":
                    subfolder_path = os.path.join(current_path, item["name"])
                    subfolder_files = self.fetch_all_files(item["id"], subfolder_path)
                    all_files.extend(subfolder_files)
                else:
                    all_files.append({"id": item["id"], "name": item["name"], "path": current_path})

            return all_files
        except Exception as e:
            print(f"Error fetching file list: {e}")
            return []

    def download_file(self, file_id, file_name, output_dir, relative_path):
        base_url = "https://www.googleapis.com/drive/v3/files"
        session = requests.Session()

        url = f"{base_url}/{file_id}?alt=media"
        headers = {"Authorization": f"Bearer {self.service._http.credentials.token}"}

        full_path = os.path.join(output_dir, relative_path)
        os.makedirs(full_path, exist_ok=True)

        try:
            file_path = self.get_filename(full_path, file_name)
            if file_path:  # Kiểm tra file_path trước khi gọi save_file()
                with session.get(url, headers=headers, stream=True) as response:
                    response.raise_for_status()
                    self.save_file(response, file_path)
        except requests.exceptions.RequestException as e:
            print(f"Failed to download {file_name}: {e}")

    def get_filename(self, full_path, file_name):
        """Xử lý tên file dựa trên lựa chọn."""
        base_name, ext = os.path.splitext(file_name)
        path = os.path.join(full_path, file_name)

        if not os.path.exists(path):
            return path  # File chưa tồn tại, trả về đường dẫn

        if self.file_exists_action.get() == "skip":
            return None  # Bỏ qua file

        elif self.file_exists_action.get() == "replace":
            return path  # Ghi đè file

        elif self.file_exists_action.get() == "rename":
            counter = 1
            new_path = os.path.join(full_path, f"{base_name} ({counter}){ext}")
            while os.path.exists(new_path):
                counter += 1
                new_path = os.path.join(full_path, f"{base_name} ({counter}){ext}")
            return new_path  # Trả về đường dẫn mới

    def save_file(self, response, file_path):
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        with open(file_path, "wb") as f:
            for chunk in response.iter_content(32768):
                if not self.downloading:
                    break
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    percentage = downloaded / total_size * 100 if total_size > 0 else 0
                    if downloaded == total_size:
                        # Tải xuống hoàn thành, in ra dòng mới
                        print(f"Downloaded {os.path.basename(file_path)}: {percentage:.2f}%")
                    else:
                        # Tải xuống chưa hoàn thành, ghi đè dòng hiện tại
                        print(f"Downloading {os.path.basename(file_path)}: {percentage:.2f}%", end="\r")

        if os.path.getsize(file_path) != total_size:
            print(f"Warning: File size mismatch for {file_path}. Retrying download.")
            os.remove(file_path)

    def get_unique_filename(self, full_path, file_name):
        base_name, ext = os.path.splitext(file_name)
        path = os.path.join(full_path, file_name)
        counter = 1
        while os.path.exists(path):
            path = os.path.join(full_path, f"{base_name} ({counter}){ext}")
            counter += 1
        return path

    def save_download_state(self):
        try:
            download_state = {
                "folder_links": self.folder_links,
                "save_path": self.save_path.get(),
                "file_list": self.file_list,
                "current_file": self.current_file
            }
            with open(self.download_state_file, "wb") as f:
                pickle.dump(download_state, f)
        except Exception as e:
            print(f"Error saving download state: {e}")

    def restore_download_state(self):
        try:
            with open(self.download_state_file, "rb") as f:
                download_state = pickle.load(f)
            self.folder_links = download_state.get("folder_links", [])
            self.save_path.set(download_state.get("save_path", ""))
            self.file_list = download_state.get("file_list", [])
            self.current_file = download_state.get("current_file", None)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Error restoring download state: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = DownloaderApp(root)
    root.mainloop()
