import os
import requests
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
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
        self.downloaded_files = set()  # Store downloaded files
        self.file_exists_action = tk.StringVar(value="skip")  # Variable to store file handling action

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

        # Add options for handling duplicate files
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

        tk.Button(button_frame, text="Start", command=self.start_download, bg="orange", fg="black").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Pause", command=self.pause_download, bg="orange", fg="black").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Resume", command=self.resume_download, bg="orange", fg="black").pack(side=tk.LEFT, padx=5)
        
        # Add Export and Import buttons
        export_import_frame = tk.Frame(root, bg="gray")
        export_import_frame.pack(pady=5)
        
        tk.Button(export_import_frame, text="Export", command=self.export_list, bg="orange", fg="black").pack(side=tk.LEFT, padx=5)
        tk.Button(export_import_frame, text="Import", command=self.import_list, bg="orange", fg="black").pack(side=tk.LEFT, padx=5)

        self.status_label = tk.Label(root, text="Status: Waiting to start...", fg="blue", bg="gray")
        self.status_label.pack(pady=5)

        self.service = self.initialize_drive_service()

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
                with open(file_path, "r", encoding="utf-8") as file:
                    links = file.readlines()
                    self.folder_links.extend(link.strip() for link in links if link.strip())
                messagebox.showinfo("Info", f"Successfully loaded {len(links)} links from file.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load links: {e}")

    def export_list(self):
        try:
            file_path = filedialog.asksaveasfilename(defaultextension=".txt")
            if not file_path:
                return

            with open(file_path, "w", encoding="utf-8") as f:
                for folder_link in self.folder_links:
                    folder_id = self.extract_folder_id(folder_link)
                    folder_name = self.get_folder_name(folder_id)
                    f.write(f"{folder_link}\t{folder_name}\n")

                    for file in self.fetch_all_files(folder_id):
                        if file['name'] in self.downloaded_files:
                            f.write(f"\t{file['path']}/{file['name']}\n")

            messagebox.showinfo("Info", "List has been successfully exported!")
        except Exception as e:
            messagebox.showerror("Error", f"Error exporting list: {e}")

    def import_list(self):
        try:
            file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
            if not file_path:
                return

            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            self.folder_links = []
            self.downloaded_files = set()

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if not line.startswith("\t"):
                    parts = line.split("\t")
                    if len(parts) == 2:
                        link, _ = parts
                        self.folder_links.append(link)
                else:
                    file_path = line.lstrip("\t")
                    file_name = os.path.basename(file_path)
                    self.downloaded_files.add(file_name)

            messagebox.showinfo("Info", "List has been successfully imported!")
        except Exception as e:
            messagebox.showerror("Error", f"Error importing list: {e}")

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

                self.file_list = self.fetch_all_files(folder_id, current_path=folder_name)
                if not self.file_list:
                    messagebox.showerror("Error", f"No files found in folder: {folder_link}")
                    continue

                self.status_label.config(text=f"Found {len(self.file_list)} files. Starting download...", fg="green")

                for file in self.file_list:
                    if not self.downloading:
                        break
                    if file['name'] in self.downloaded_files:
                        continue  # Skip already downloaded files
                    self.download_file(file["id"], file["name"], os.path.join(self.save_path.get(), file['path']))

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
                    subfolder_files = self.fetch_all_files(item["id"], current_path=subfolder_path)
                    all_files.extend(subfolder_files)
                else:
                    all_files.append({"id": item["id"], "name": item["name"], "path": current_path})

            return all_files
        except Exception as e:
            print(f"Error fetching file list: {e}")
            return []

    def download_file(self, file_id, file_name, output_dir):
        base_url = "https://www.googleapis.com/drive/v3/files"
        session = requests.Session()

        url = f"{base_url}/{file_id}?alt=media"
        headers = {"Authorization": f"Bearer {self.service._http.credentials.token}"}

        full_path = self.get_filename(output_dir, file_name)
        if not full_path:
            return  # Skip if no download needed

        try:
            os.makedirs(output_dir, exist_ok=True)  # Ensure directory exists
            with session.get(url, headers=headers, stream=True) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(full_path, "wb") as f:
                    for chunk in response.iter_content(32768):
                        if not self.downloading:
                            break
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            percentage = (downloaded / total_size) * 100 if total_size > 0 else 0
                            print(f"Downloading {file_name}: {percentage:.2f}%", end="\r")
                print(f"Downloaded {file_name} successfully.")
            self.downloaded_files.add(file_name)  # Save successfully downloaded file
        except requests.exceptions.RequestException as e:
            print(f"Failed to download {file_name}: {e}")

    def get_filename(self, output_dir, file_name):
        base_name, ext = os.path.splitext(file_name)
        path = os.path.join(output_dir, file_name)

        if os.path.exists(path):
            if self.file_exists_action.get() == "skip":
                return None  # Skip file
            elif self.file_exists_action.get() == "replace":
                return path  # Overwrite file
            elif self.file_exists_action.get() == "rename":
                counter = 1
                while os.path.exists(path):
                    path = os.path.join(output_dir, f"{base_name} ({counter}){ext}")
                    counter += 1
        return path

    def pause_download(self):
        self.downloading = False
        self.status_label.config(text="Download paused...", fg="orange")

    def resume_download(self):
        if not self.downloading:
            self.downloading = True
            self.status_label.config(text="Resuming download...", fg="green")
            threading.Thread(target=self.process_links).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = DownloaderApp(root)
    root.mainloop()
