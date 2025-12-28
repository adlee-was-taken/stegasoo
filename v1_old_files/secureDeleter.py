import os
import shutil
import random

class SecureDeleter:
    def __init__(self, path):
        self.path = path

    def overwrite_file(self, file_path, passes=7):
        """Overwrites the file with multiple patterns and random data."""
        patterns = [b'\x00', b'\xFF', random.randbytes(1)]
        print(patterns)
        length = os.path.getsize(file_path)
        for _ in range(passes):
            with open(file_path, "r+b") as file:
                for pattern in patterns:
                    file.seek(0)
                    for _ in range(length):
                        file.write(pattern)
                # Final pass with random data for each byte
                file.seek(0)
                file.write(random.randbytes(length))

    def delete_file(self, file_path):
        """Securely deletes a file."""
        if os.path.isfile(file_path):
            self.overwrite_file(file_path)
            os.remove(file_path)

    def delete_folder(self, folder_path):
        """Securely deletes a folder and its contents."""
        if os.path.isdir(folder_path):
            for root, dirs, files in os.walk(folder_path, topdown=False):
                for name in files:
                    file_path = os.path.join(root, name)
                    self.delete_file(file_path)
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            shutil.rmtree(folder_path)\

    def wipe_free_space(self, drive, size=1024*1024*10): # 10MB default file size
        """Writes temporary files with random data to overwrite free disk space."""
        temp_files = []
        try:
            while True:
                temp_file = os.path.join(drive, f"temp_{random.randint(0, 999999)}.dat")
                with open(temp_file, "wb") as file:
                    file.write(random.randbytes(size))
                temp_files.append(temp_file)
        except OSError:  # Typically disk full
            for temp_file in temp_files:
                os.remove(temp_file)

    def execute(self):
        """Determines whether the path is a file or folder and deletes it securely."""
        if os.path.isfile(self.path):
            self.delete_file(self.path)
        elif os.path.isdir(self.path):
            self.delete_folder(self.path)
        else:
            print("Path does not exist.")

# Usage example:
#deleter = SecureDeleter("/path/to/your/file_or_folder")
#deleter.execute()
