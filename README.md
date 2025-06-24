# 🎭 Antic Browser ![Flutter](https://img.shields.io/badge/Flutter-%2302569B.svg?style=for-the-badge&logo=Flutter&logoColor=white)

Trình duyệt chống nhận dạng mã nguồn mở miễn phí được xây dựng bằng Flutter

## ⚙️ Danh sách tùy chỉnh hồ sơ

| Thiết lập             | Có thể thay đổi |
| ------------------------------ | ----- |
| *User Agent*                   | ✅    |
| *Độ phân giải màn hình*            | ✅    |
| *Múi giờ*                 | ✅    |
| *Ngôn ngữ*                         | ✅    |
| *Bật/tắt WebGL*     | ✅    |
| *Nhà sản xuất*                | ✅    |
| *Số luồng CPU*        | ✅    |
| *RAM*           | ✅    |
| *Giả lập cảm ứng*             | ✅    |

## 📥 Cài đặt
```sh
git clone https://github.com/clienthold/Antic-Browser.git
cd Antic-Browser
pip3 install -r requirements.txt
playwright install
```

## ✨ Ảnh chụp màn hình
![Screenshot](https://github.com/user-attachments/assets/8c38bdea-5e46-4925-b92f-0c00feb2ab14)
![Screenshot](https://github.com/user-attachments/assets/1aee35f4-7075-415a-bbcf-46aa5635d89c)

## 🏗️ Build EXE
Để đóng gói ứng dụng thành file thực thi, cài đặt thêm `flet-cli` và `PyInstaller` rồi chạy:
```sh
pip install flet-cli PyInstaller
flet pack antic.py
```
Tệp kết quả sẽ nằm trong thư mục `dist/`.
Khi xây dựng trên Windows file tạo ra có phần mở rộng `.exe`.
