# Import
import logging
import os
import threading
import socket
import ssl
import sys
import re
from urllib.parse import urlparse
# ----------------------------------------------------------
# ----------------------------------------------------------

# Kiểm tra URL hợp lệ


def is_anURL(URL):
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        # domain...
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, URL) is not None

# --------------------------------------------  --------------

# Tạo Folder


def createFolder(directory):
    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
    except OSError:
        print('Lỗi tạo FILE : ' + directory)
        sys.exit(0)

# ----------------------------------------------------------

# Kiểm tra File hay Folder


def is_File(URL):
    split_URL = URL.split("/")
    if len(split_URL) > 4 and split_URL[-1] == '':
        return False
    else:
        return True

# ----------------------------------------------------------

# Lấy Status Code từ Header


def get_StatusCode(Response):
    Header_asString = Response.decode("utf-8")
    StatusCode = Header_asString[9] + \
        Header_asString[10] + Header_asString[11]
    return int(StatusCode)

# ----------------------------------------------------------

# Lấy Header từ Dữ liệu thu vào


def get_Header(Response):
    End_ofHeader = Response.find(b'\r\n\r\n')
    return Response[0:End_ofHeader]

# ----------------------------------------------------------

# Kiểm tra có phải kiểu dữ liệu Chunked


def is_Chunked(Header):
    return Header.find(b'Transfer-Encoding: chunked') != -1

# ----------------------------------------------------------

# Lấy Content - Length


def get_ContentLength(Header):
    Header_asString = str(Header, 'utf-8')
    ContentLength_Start = Header_asString.find('Content-Length: ')

    if ContentLength_Start == -1:
        return -1
    else:
        # Nhảy 16 ô để lấy số
        ContentLength_Start += 16
        Index = ContentLength_Start
        ContentLength = ''
        while Header_asString[Index] != '\r':
            ContentLength += Header_asString[Index]
            Index += 1
        return int(ContentLength)

# ----------------------------------------------------------

# Lấy Content không phải Chunk


def get_ContentUnchunked(Sock, Raw_Data, ContentLength):
    # Xử lí khi có Content - Length
    socket.setdefaulttimeout(5)
    if (ContentLength != -1):
        while len(Raw_Data) < ContentLength:
            try:
                Raw_Data += Sock.recv(4096)
            except socket.timeout:
                print("Lỗi time - out!")
                Sock.close()
                sys.exit(0)

    # Xử lí khi không có Content - Length
    else:
        while Raw_Data.find(b'</html>\r\n' == -1):
            try:
                Raw_Data += Sock.recv(4096)
            except socket.timeout:
                print("Lỗi time - out!")
                Sock.close()
                sys.exit(0)
    return Raw_Data

# ----------------------------------------------------------

# Lấy Size của file Chunk chuyển sang Integer


def get_ChunkSize(Response):
    Size_End = Response.find(b'\r\n')
    if Size_End == -1:
        return -1
    Size_String = str(Response[0:Size_End], 'utf-8')
    try:
        return int(Size_String, 16)
    except ValueError:
        return -1

# ----------------------------------------------------------

# Lấy Content Chunk - Đã tách Header


def get_ContentChunked(Sock, Raw_Data):
    # Lấy dữ liệu ra
    Content = b''
    Start = 0
    socket.setdefaulttimeout(5)
    # Mở rộng Size đến khi đọc được Chunk Size
    while Raw_Data.find(b'\r\n') == -1:
        try:
            Raw_Data += Sock.recv(4096)
        except socket.timeout:
            print("Lỗi time - out!")
            Sock.close()
            sys.exit(0)
    End = Raw_Data.find(b'\r\n')
    ChunkSize = get_ChunkSize(Raw_Data[Start:End + 2])
    Raw_Data = Raw_Data[End + 2:]

    while ChunkSize != 0:
        while len(Raw_Data) < ChunkSize:
            try:
                Raw_Data += Sock.recv(4096)
            except socket.timeout:
                print("Lỗi time - out!")
                Sock.close()
                sys.exit(0)

        # Chuyển dữ liệu qua Content
        Content += Raw_Data[:ChunkSize]
        # Bỏ \r\n và Content đã rút
        Raw_Data = Raw_Data[ChunkSize + 2:]

        while Raw_Data.find(b'\r\n') < 0:
            try:
                Raw_Data += Sock.recv(4096)
            except socket.timeout:
                print("Lỗi time - out!")
                Sock.close()
                sys.exit(0)

        ChunkSize = get_ChunkSize(Raw_Data)
        Raw_Data = Raw_Data[Raw_Data.find(b'\r\n') + 2:]
    return Content

# ----------------------------------------------------------

# Lấy Content tạo lại socket


def get_Content(URL, Header):
    # Gán giá trị Port
    Server_Port = 80
    socket.setdefaulttimeout(5)
    # Xử lí URL
    Parse_URL = urlparse(URL)
    Host = Parse_URL.hostname
    Path = Parse_URL.path

    # Thêm '/' cho Path
    if Path == '':
        Path = '/'

    # Kết nối socket
    Sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        Sock.connect((Host, Server_Port))
        # Xử lí request
        Request = ('GET ' + Path + ' HTTP/1.1\r\nHost: ' + Host +
                   '\r\nConnection: close\r\n\r\n').encode('ascii')

        # Gửi request
        Sock.send(Request)
        # Nhận dữ liệu
        try:
            Response = Sock.recv(4096)
        except socket.timeout:
            print("Lỗi time - out!")
            Sock.close()
            sys.exit(0)

        while Response.find(b'\r\n\r\n') == -1:
            try:
                Response = Sock.recv(4096)
            except socket.timeout:
                print("Lỗi time - out!")
                Sock.close()
                sys.exit(0)

        # Xử lí response
        Header = get_Header(Response)
        Status = get_StatusCode(Header)
        Content = Response[len(Header) + 4:]

        # Error 404
        if Status >= 400:
            return None
        # Xử lí trường hợp 301
        elif Status == 301:
            return None
        # Trường hợp 302 và 200
        elif Status == 302 or Status == 200:
            # Xử lí Chunked
            if is_Chunked(Header):
                return get_ContentChunked(Sock, Content)
            # Xử lí unChunked
            else:
                return get_ContentUnchunked(Sock, Content, get_ContentLength(Header))
        # Xử lí các trường hợp còn lại
        else:
            return None

    except socket.error:
        print("Lỗi kết nối!")
        Sock.close()
        sys.exit(0)


# ----------------------------------------------------------

# Tải file tạo lại Socket


def download_File(Folder, URL):
    Header = b''
    Content = get_Content(URL, Header)
    # Xử lí tên file lưu
    Parse_URL = urlparse(URL)
    Host = Parse_URL.hostname
    Path = Parse_URL.path

    ContentType = str(get_ContentType(Header), 'utf-8')

    if not is_Chunked(Header) or (ContentType == "text"):
        if Path == '':
            FileName = ''
        else:
            NoTreatment, FileName = Path.rsplit('/', 1)
        if FileName == '':
            FileName = f"{Host}" + "_index.html"
        elif FileName.find(".html") == -1 and is_Chunked(Header):
            FileName = f"{Host}" + "_" + FileName + ".html"
        else:
            FileName = f"{Host}" + "_" + FileName
    elif is_Chunked(Header) and ContentType == "image":
        ExtensionName = str(get_ExtensionName(Header), 'utf-8')
        NoTreatment, FileName = Path.rsplit('/', 1)
        FileName, NoTreatment = FileName.rsplit('.', 1)
        FileName = f"{Host}" + "_" + FileName + "." + ExtensionName

    # Xử lí lưu
    Destination = f"{Folder}/{FileName}"
    open(Destination, "wb").write(Content)
    print(f'Tải thành công {Destination}')

# ----------------------------------------------------------

# Lấy Content sử dụng Socket cũ


def get_ContentFolder(Sock, URL, Header):
    socket.setdefaulttimeout(5)
    # Nhận dữ liệu
    try:
        Response = Sock.recv(4096)
    except socket.timeout:
        print("Lỗi time - out!")
        Sock.close()
        sys.exit(0)

    while Response.find(b'\r\n\r\n') == -1:
        try:
            Response = Sock.recv(4096)
        except socket.timeout:
            print("Lỗi time - out!")
            Sock.close()
            sys.exit(0)

    # Xử lí response
    Header = get_Header(Response)
    Status = get_StatusCode(Header)
    Content = Response[len(Header) + 4:]

    # Error 404
    if Status >= 400:
        return None
    # Xử lí trường hợp 301
    elif Status == 301:
        return None
    # Trường hợp 302 và 200
    elif Status == 302 or Status == 200:
        # Xử lí Chunked
        if is_Chunked(Header):
            return get_ContentChunked(Sock, Content)
        # Xử lí unChunked
        else:
            return get_ContentUnchunked(Sock, Content, get_ContentLength(Header))
    # Xử lí các trường hợp còn lại
    else:
        return None

# ----------------------------------------------------------

# Tải file sử dụng Socket cũ


def download_Folder(Sock, Folder, URL):
    Header = b''
    # Xử lí tên file lưu
    Parse_URL = urlparse(URL)
    Host = Parse_URL.hostname
    Path = Parse_URL.path

    if Path == '':
        Path = '/'
    Request = ('GET ' + Path + ' HTTP/1.1\r\nHost: ' + Host +
               '\r\nConnection: keep-alive\r\n\r\n').encode('ascii')
    Sock.send(Request)

    Content = get_ContentFolder(Sock, URL, Header)
    ContentType = str(get_ContentType(Header), 'utf-8')

    if not is_Chunked(Header) or (ContentType == "text"):
        if Path == '':
            FileName = ''
        else:
            NoTreatment, FileName = Path.rsplit('/', 1)
        if FileName == '':
            FileName = f"{Host}" + "_index.html"
        elif FileName.find(".html") == -1 and is_Chunked(Header):
            FileName = f"{Host}" + "_" + FileName + ".html"
        else:
            FileName = f"{Host}" + "_" + FileName

    elif is_Chunked(Header) and ContentType == "image":
        ExtensionName = str(get_ExtensionName(), 'utf-8')
        NoTreatment, FileName = Path.rsplit('/', 1)
        FileName, NoTreatment = FileName.rsplit('.', 1)
        FileName = f"{Host}" + "_" + FileName + "." + ExtensionName

    # Xử lí lưu
    Destination = f"{Folder}/{FileName}"
    open(Destination, "wb").write(Content)
    print(f'Tải thành công {Destination}')

# ----------------------------------------------------------

# Xử lí đơn lẻ thread cho Folder


def download_CompletedFolder(Folder, URL):
    Sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    Parse_URL = urlparse(URL)
    Host = Parse_URL.hostname
    Path = Parse_URL.path
    Header = b''
    # Tạo folder
    FolderName, NoTreatment = Path.rsplit('/', 1)
    NoTreatment, FolderName = FolderName.rsplit('/', 1)
    FolderName = f"{Host}" + "_" + FolderName
    FolderDir = Folder + '\\' + FolderName
    createFolder(Folder + '/' + FolderName + '/')

    # Khởi tạo Socket
    try:
        Sock.connect((Host, 80))
        if Path == '':
            Path = '/'
        Request = ('GET ' + Path + ' HTTP/1.1\r\nHost: ' + Host +
                   '\r\nConnection: keep-alive\r\n\r\n').encode('ascii')
        Sock.send(Request)
        ContentMainFolder = get_ContentFolder(Sock, URL, Header)
        Link = get_LinkList(ContentMainFolder, URL)

        threadFolder = []
        for eachs in Link:
            download_Folder(Sock, FolderDir, eachs)
        Sock.close()

    except socket.error:
        print("Lỗi kết nối!")
        Sock.close()
        sys.exit(0)

# ----------------------------------------------------------

# Kiểm tra URL hợp lệ


def is_AvailableURL(URL, Add):
    Character = ["=", "?"]
    Start = 4
    if URL.find(Add) != -1:
        return False
    if Add.find("http") != -1:
        return False
    for x in Character:
        if Add.find(x) != -1:
            return False
    return True

# ----------------------------------------------------------

# Xử lí chuỗi file tải về


def get_LinkList(Content, URL):
    LinkList = []
    Start = 0
    # Thêm từng Link vào mảng
    while True:
        Start = Content.find(b'a href=', Start)
        End = Content.find(b'">', Start)
        if Start == -1:
            break
        URL_Add = URL + Content[Start + 8:End].decode()
        # Kiểm tra URL hợp lệ
        if is_AvailableURL(URL, Content[Start + 8:End].decode()) == False:
            Start += 1
            continue
        else:
            LinkList.append(URL_Add)
        Start += 1
    return LinkList

# ----------------------------------------------------------

# Lấy Content - type


def get_ContentType(Header):
    Character = [b'\r', b';']
    Start = Header.find(b'Content-Type:')
    Start = Header.find(b' ', Start)
    End = Header.find(b'/', Start)
    return Header[Start + 1:End]

# ----------------------------------------------------------

# Lấy Extension File Name


def get_ExtensionName(Header):
    Characters = [b';', b'\r']
    Start = Header.find(b'Content-Type: ')
    Start = Header.find(b'/', Start)

    if Header.find(b'\r', Start) < Header.find(b';', Start):
        End = Header.find(b'\r', Start)
    elif Header.find(b';', Start) == -1:
        End = Header.find(b'\r', Start)
    else:
        End = Header.find(b';', Start)
    return Header[Start + 1:End]

# ----------------------------------------------------------

# Main


def run():
    Folder = '.'

    URL = {"http://www.httpwatch.com/httpgallery/chunked/chunkedimage.aspx"
           "http://web.stanford.edu/dept/its/support/techtraining/techbriefing-media/Intro_Net_91407.ppt",
           "http://web.stanford.edu/class/cs231a/course_notes/"}
    Number = len(sys.argv)
    global Header

    ListThread = []
    for i in URL:
        if is_anURL(i) == True:
            if is_File(i) == True:
                thread = threading.Thread(
                    target=download_File, args=(Folder, i))
            else:
                thread = threading.Thread(
                    target=download_CompletedFolder, args=(Folder, i))
            thread.start()
            ListThread.append(thread)
        else:
            print("Lỗi hình thức : " + i)
    for each in ListThread:
        each.join()
    print("Xử lí xong.")


# ----------------------------------------------------------
run()
