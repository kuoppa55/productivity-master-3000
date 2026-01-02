from PIL import Image

img = Image.open("C:\\Users\\tthku\\Documents\\productivity-master-3000\\productivity_master_3000\\PM3000_Raw.png")

img.save("PM3000_icon.ico", sizes=[(16,16),(32,32),(64,64),(128,128),(256,256)])