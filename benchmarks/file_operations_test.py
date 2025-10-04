#!/usr/bin/env python3
"""
Simple file operations benchmark for testing kernel trace capture.

This benchmark performs common file I/O operations to generate
a variety of syscalls: open, read, write, close, stat, etc.
"""

import os
import sys
import time
import tempfile
import shutil

def create_test_files(base_dir, num_files=10):
    """Create multiple test files with content."""
    print(f"Creating {num_files} test files in {base_dir}")
    files = []
    
    for i in range(num_files):
        filepath = os.path.join(base_dir, f"test_file_{i}.txt")
        with open(filepath, 'w') as f:
            # Write some content - generates write syscalls
            content = f"Test file {i}\n" * 100
            f.write(content)
        files.append(filepath)
    
    return files

def read_files(files):
    """Read all files - generates read syscalls."""
    print(f"Reading {len(files)} files")
    total_bytes = 0
    
    for filepath in files:
        with open(filepath, 'r') as f:
            content = f.read()
            total_bytes += len(content)
    
    print(f"Read {total_bytes} bytes total")
    return total_bytes

def stat_files(files):
    """Stat all files - generates stat/fstat syscalls."""
    print(f"Stating {len(files)} files")
    
    for filepath in files:
        stat_info = os.stat(filepath)
        size = stat_info.st_size
    
    print("File stat operations completed")

def append_to_files(files):
    """Append to files - generates open, write, close syscalls."""
    print(f"Appending to {len(files)} files")
    
    for filepath in files:
        with open(filepath, 'a') as f:
            f.write(f"Appended data at {time.time()}\n")
    
    print("Append operations completed")

def copy_files(files, dest_dir):
    """Copy files - generates lots of read/write syscalls."""
    print(f"Copying {len(files)} files to {dest_dir}")
    
    copied_files = []
    for filepath in files:
        basename = os.path.basename(filepath)
        dest_path = os.path.join(dest_dir, f"copy_{basename}")
        shutil.copy2(filepath, dest_path)
        copied_files.append(dest_path)
    
    print("Copy operations completed")
    return copied_files

def delete_files(files):
    """Delete files - generates unlink syscalls."""
    print(f"Deleting {len(files)} files")
    
    for filepath in files:
        if os.path.exists(filepath):
            os.remove(filepath)
    
    print("Delete operations completed")

def main():
    print("=" * 60)
    print("File Operations Benchmark")
    print("=" * 60)
    print()
    
    # Create temporary directories
    base_dir = tempfile.mkdtemp(prefix="fileops_test_")
    copy_dir = tempfile.mkdtemp(prefix="fileops_copy_")
    
    print(f"Working directory: {base_dir}")
    print(f"Copy directory: {copy_dir}")
    print()
    
    try:
        # Phase 1: Create files
        print("PHASE 1: Creating files")
        files = create_test_files(base_dir, num_files=20)
        time.sleep(0.5)
        print()
        
        # Phase 2: Read files
        print("PHASE 2: Reading files")
        read_files(files)
        time.sleep(0.5)
        print()
        
        # Phase 3: Stat files
        print("PHASE 3: Getting file statistics")
        stat_files(files)
        time.sleep(0.5)
        print()
        
        # Phase 4: Append to files
        print("PHASE 4: Appending to files")
        append_to_files(files)
        time.sleep(0.5)
        print()
        
        # Phase 5: Copy files
        print("PHASE 5: Copying files")
        copied_files = copy_files(files, copy_dir)
        time.sleep(0.5)
        print()
        
        # Phase 6: Read copied files
        print("PHASE 6: Reading copied files")
        read_files(copied_files)
        time.sleep(0.5)
        print()
        
        # Phase 7: Cleanup
        print("PHASE 7: Cleaning up")
        delete_files(files)
        delete_files(copied_files)
        print()
        
        print("=" * 60)
        print("Benchmark completed successfully")
        print("=" * 60)
        
    finally:
        # Clean up directories
        try:
            shutil.rmtree(base_dir)
            shutil.rmtree(copy_dir)
        except:
            pass

if __name__ == "__main__":
    main()
