# Ứng Dụng Dịch Sách & Tài Liệu Dài Full Tiếng Việt

Trang web chuyên biệt dành cho dịch thuật toàn bộ các tệp tài liệu và sách dài bất kể độ dài (từ vài trang đến hàng nghìn trang) sang Tiếng Việt.

---

## 🌟 Tính Năng Nổi Bật

1. **Bất kể độ dài (Unlimited Length)**:
   - Cơ chế chia khối thông minh (Smart Batch Chunking) theo câu và đoạn văn tự nhiên.
   - Xử lý tiến trình chạy nền (Background Worker) không lo timeout trình duyệt hay đứt mạng.
   - Thống kê thời gian thực: % tiến độ, số đoạn đã dịch, số từ, tốc độ từ/phút và thời gian còn lại (ETA).

2. **Hỗ Trợ Toàn Diện Tệp Word & PDF**:
   - **Word (.docx)**: Giữ nguyên cấu trúc đề mục (Heading 1, 2, 3), các đoạn văn, danh sách và bảng biểu (Tables).
   - **PDF (.pdf)**: Trích xuất thông minh, ghép nối các dòng ngắt giữa chừng và xuất ra file PDF chuẩn font tiếng Việt hoặc Word.
   - **Text (.txt / .md)**: Hỗ trợ văn bản thuần.

3. **Đa Dạng Định Dạng Tải Về**:
   - 📘 **Tải file Word (.docx)**: Chuẩn định dạng gốc đã dịch toàn bộ sang tiếng Việt.
   - 📕 **Tải file PDF (.pdf)**: Tạo file PDF font Arial A4 rõ nét, không lỗi font tiếng Việt.
   - 📙 **Tải file Song Ngữ (.docx)**: Hiển thị song song câu tiếng Việt và câu tiếng Anh gốc (rất hữu ích cho người học và đối chiếu).
   - 📄 **Tải file Text (.txt)**: Bản dịch thuần UTF-8 nhẹ.

4. **Trình Đọc Văn Bản Tương Tác Trực Tiếp (Interactive Reader)**:
   - Đọc trực tiếp trên web với 2 chế độ: *Chỉ Tiếng Việt* hoặc *Song ngữ so sánh 2 cột*.
   - Tìm kiếm từ khóa theo thời gian thực (Live Search & Highlight).
   - Nút sao chép toàn bộ bản dịch chỉ với 1 click.

5. **2 Cơ Chế Dịch Thuật**:
   - **Google Dịch Tự Động (Mặc định)**: Hoàn toàn miễn phí 100%, không cần tài khoản hay API key.
   - **Google Gemini Flash AI (Tùy chọn)**: Hỗ trợ người dùng nhập Gemini API Key để dịch sách văn học, tiểu thuyết với câu chữ trau chuốt, tự nhiên nhất.

---

## 🚀 Cách Truy Cập & Sử Dụng

- **Link truy cập:** [http://localhost:5000](http://localhost:5000)
- Nếu muốn khởi động lại hệ thống sau này: Chỉ cần bấm đúp chuột vào file `run.bat` trong thư mục này.
