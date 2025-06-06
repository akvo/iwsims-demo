from uuid import uuid4
from utils import storage


def upload_file(file, filename, folder="uploads"):
    temp_file = open(f"./tmp/{filename}", "wb+")
    for chunk in file.chunks():
        temp_file.write(chunk)
    storage.upload(file=f"./tmp/{filename}", filename=filename, folder=folder)
    temp_file.close()


def handle_upload(request, folder="uploads"):
    """
    Process the uploaded file and save it with a new name.
    The new name is generated by appending a UUID to the original filename.
    """
    file = request.FILES["file"]
    extension = file.name.split(".")[-1]
    original_filename = "-".join(file.name.split(".")[:-1])
    original_filename = "_".join(original_filename.strip().split(" "))
    new_filename = f"{original_filename}-{uuid4()}.{extension}"
    upload_file(
        file=file,
        filename=new_filename,
        folder=folder,
    )
    return new_filename
