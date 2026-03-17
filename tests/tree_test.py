import tkinter as tk
from tkinter import ttk

root = tk.Tk()
tree = ttk.Treeview(root)
tree.pack()

# Test IID case sensitivity
tree.insert("", "end", iid="C:\\Test", text="Upper")
exists_lower = tree.exists("c:\\test")
exists_upper = tree.exists("C:\\Test")

print(f"IID 'C:\\Test' exists (exact match): {exists_upper}")
print(f"IID 'c:\\test' exists (case mismatch): {exists_lower}")

try:
    tree.insert("c:\\test", "end", iid="dummy", text="Child under lower")
    print("Success: Inserted child under lowercase IID")
except Exception as e:
    print(f"Failure: Could not insert under lowercase IID: {e}")

root.destroy()
