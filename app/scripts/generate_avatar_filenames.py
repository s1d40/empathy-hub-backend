



def generate_filenames():
    avatar_filenames = []
    # To generate 200 filenames, assuming they are named 0.jpg through 69.jpg
    # Adjust the range if your naming or count is different.
    for i in range(200): # Generates 0, 1, ..., 69 (total 70 files)
        avatar_filenames.append(f"{i}.jpg")

    return avatar_filenames


avatar_filenames = generate_filenames()