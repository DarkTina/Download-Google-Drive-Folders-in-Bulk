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

        # Variables
        self.folder_links = []
        self.save_path = tk.StringVar()
        self.downloading = False
        self.file_list = []

        # UI Components
        tk.Label(root, text="Google Drive Folder Link:", bg="gray", fg="white").pack(pady=5)
        self.link_entry = tk.Entry(root, width=50)
        self.link_entry.pack(pady=5)

        tk.Button(root, text="Add Link", command=self.add_link, bg="orange", fg="black").pack(pady=5)
        tk.Button(root, text="Load Links from TXT", command=self.load_links_from_txt, bg="orange", fg="black").pack(pady=5)

        tk.Label(root, text="Save Path:", bg="gray", fg="white").pack(pady=5)
        tk.Entry(root, textvariable=self.save_path, width=50).pack(pady=5)
        tk.Button(root, text="Choose Path", command=self.choose_save_path, bg="orange", fg="black").pack(pady=5)

        tk.Button(root, text="Start", command=self.start_download, bg="orange", fg="black").pack(pady=5)
        tk.Button(root, text="Pause", command=self.pause_download, bg="orange", fg="black").pack(pady=5)

        # Status display
        self.status_label = tk.Label(root, text="Status: Waiting to start...", fg="blue", bg="gray")
        self.status_label.pack(pady=5)

        # Initialize Google Drive API service
        self.service = self.initialize_drive_service()

    def initialize_drive_service(self):
        """Authenticate and initialize Google Drive API service."""
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

        # Process each folder link
        threading.Thread(target=self.process_links).start()

    def process_links(self):
        try:
            for folder_link in self.folder_links:
                if not self.downloading:
                    break

                # Extract folder ID from the link
                folder_id = self.extract_folder_id(folder_link)
                if not folder_id:
                    messagebox.showerror("Error", f"Invalid folder link: {folder_link}")
                    continue

                # Get folder name from Google Drive API
                folder_name = self.get_folder_name(folder_id)
                if not folder_name:
                    messagebox.showerror("Error", f"Failed to fetch folder name for: {folder_link}")
                    continue

                # Create a directory with the folder name
                target_path = os.path.join(self.save_path.get(), folder_name)
                os.makedirs(target_path, exist_ok=True)

                # Fetch all files recursively
                self.file_list = self.fetch_all_files(folder_id)
                if not self.file_list:
                    messagebox.showerror("Error", f"No files found in folder: {folder_link}")
                    continue

                self.status_label.config(text=f"Found {len(self.file_list)} files. Starting download...", fg="green")

                for file in self.file_list:
                    if not self.downloading:
                        break
                    start_time = time()
                    self.download_file(file["id"], file["name"], target_path, file["path"])
                    elapsed_time = time() - start_time
                    print(f"Downloaded: {file['name']} in {elapsed_time:.2f} seconds")

            self.status_label.config(text="Download completed!" if self.downloading else "Paused.", fg="blue")
            self.downloading = False
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            self.status_label.config(text="Error downloading files.", fg="red")

    def extract_folder_id(self, folder_link):
        """Extract the folder ID from the Google Drive link."""
        try:
            if "folders" in folder_link:
                return folder_link.split("/folders/")[1].split("?")[0]
            return folder_link.split("/")[-1].split("?")[0]
        except IndexError:
            return None

    def get_folder_name(self, folder_id):
        """Fetch the folder name using its ID."""
        try:
            folder = self.service.files().get(fileId=folder_id, fields="name").execute()
            return folder.get("name")
        except Exception as e:
            print(f"Error fetching folder name: {e}")
            return None

    def pause_download(self):
        self.downloading = False
        self.status_label.config(text="Download paused...", fg="orange")

    def fetch_all_files(self, folder_id, current_path=""):
        """Recursively fetch all files from a folder and its subfolders."""
        try:
            all_files = []

            # Query to list files in the current folder
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="files(id, name, mimeType)"
            ).execute()

            items = results.get("files", [])

            for item in items:
                if item["mimeType"] == "application/vnd.google-apps.folder":
                    # If item is a folder, fetch its contents recursively
                    subfolder_path = os.path.join(current_path, item["name"])
                    subfolder_files = self.fetch_all_files(item["id"], subfolder_path)
                    all_files.extend(subfolder_files)
                else:
                    # Add file to the list with its relative path
                    all_files.append({"id": item["id"], "name": item["name"], "path": current_path})

            return all_files
        except Exception as e:
            print(f"Error fetching file list: {e}")
            return []

    def download_file(self, file_id, file_name, output_dir, relative_path):
        """Download a single file and place it in the correct folder."""
        base_url = "https://www.googleapis.com/drive/v3/files"
        session = requests.Session()

        # Build the URL for downloading
        url = f"{base_url}/{file_id}?alt=media"
        headers = {"Authorization": f"Bearer {self.service._http.credentials.token}"}

        # Create the full directory path
        full_path = os.path.join(output_dir, relative_path)
        os.makedirs(full_path, exist_ok=True)

        try:
            # Stream download the file
            with session.get(url, headers=headers, stream=True) as response:
                response.raise_for_status()  # Raise an error if the request failed
                self.save_file(response, file_name, full_path)
        except requests.exceptions.RequestException as e:
            print(f"Failed to download {file_name}: {e}")

    def save_file(self, response, file_name, output_dir):
        """Save the downloaded file to the specified directory."""
        file_path = os.path.join(output_dir, file_name)
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
                    print(f"Downloading {file_name}: {percentage:.2f}% - {downloaded / 1024:.2f} KB", end="\r")

        # Validate the file size
        if os.path.getsize(file_path) != total_size:
            print(f"Warning: File size mismatch for {file_name}. Retrying download.")
            os.remove(file_path)

# Run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = DownloaderApp(root)
    root.mainloop()
