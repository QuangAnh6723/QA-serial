from PyQt6 import uic, QtWidgets, QtCore
import sys
import serial.tools.list_ports
from PyQt6.QtWidgets import QFileDialog, QTableWidgetItem, QCheckBox, QWidget, QHBoxLayout
import xml.etree.ElementTree as ET
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHeaderView
import threading
import time
from PyQt6.QtCore import pyqtSignal, QObject
from datetime import datetime
from PyQt6.QtCore import QSettings
import os

def setup_serial_comboboxes(window):
    # Baudrate
    baud_list = ["9600", "19200", "38400", "57600", "115200", "921600"]
    window.Baudrate.clear()
    window.Baudrate.addItems(baud_list)
    window.Baudrate.setCurrentText("115200")  # hoặc setCurrentIndex(0)
    
    # Data bits (NData)
    data_bits_list = ["5", "6", "7", "8", "9"]
    window.NData.clear()
    window.NData.addItems(data_bits_list)
    window.NData.setCurrentText("8")
    
    # Parity
    parity_list = ["N", "E", "O", "M", "S"]  # None, Even, Odd, Mark, Space
    window.Parity.clear()
    window.Parity.addItems(parity_list)
    window.Parity.setCurrentText("N")
    
    # Stop bits
    stop_bit_list = ["1", "1.5", "2"]
    window.StopBit.clear()
    window.StopBit.addItems(stop_bit_list)
    window.StopBit.setCurrentText("1")

def setup_table_columns(window):
    table = window.tableWidgetCommands
    header = table.horizontalHeader()
    # Cột 0 ("Test"): Rộng 60px, không co giãn
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
    table.setColumnWidth(0, 60)
    # Cột 1 ("Command"): Rộng 120px, không co giãn
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
    table.setColumnWidth(1, 120)
    # Cột 2 ("Value (Hex)"): Auto-stretch (chiếm hết phần còn lại)
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

def resource_path(relative_path):
    """Lấy đường dẫn file resource cho cả khi chạy source và khi đóng gói."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class SerialReceiver(QObject):
    data_received = pyqtSignal(bytes)

class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi(resource_path("ui/main.ui"), self)
        setup_serial_comboboxes(self)
        self.scan_ports()
        # cài event filter
        self.COMPort.installEventFilter(self)
        self.pushButtonLoadXml.clicked.connect(self.load_xml_commands)
        # setup_table_columns(self)
        self.Connect.clicked.connect(self.connect_serial)
        self.serial_port = None  # Để lưu object serial
        self.setup_table_columns()
        self.Single.setChecked(True)  # Single mặc định được chọn
        self.test.clicked.connect(self.test_command)
        # self.tableWidgetCommands.cellClicked.connect(self.on_table_command_clicked)
        
        self.tableWidgetCommands.cellClicked.connect(self.on_table_cell_clicked)
        self.serial_receiver = SerialReceiver()
        self.serial_receiver.data_received.connect(self.on_serial_data_received)
        self.receive_thread = None
        self._receiving = False

        self.tableWidgetCommands.setColumnCount(4)
        self.tableWidgetCommands.setHorizontalHeaderLabels(["Test", "Command", "Expected","Value (Hex)"])
        self.Btn_clear.clicked.connect(self.clear_log)
        self.load_config()

    def scan_ports(self):
        self.COMPort.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.COMPort.addItem(port.device)

    def eventFilter(self, obj, event):
        if obj is self.COMPort and event.type() == QtCore.QEvent.Type.MouseButtonPress:
            self.scan_ports()
        return super().eventFilter(obj, event)
    
    def add_row(self, name, value, expected, row):
        # Cột 0: Checkbox
        widget = QWidget()
        checkbox = QCheckBox()
        layout = QHBoxLayout(widget)
        layout.addWidget(checkbox)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(0,0,0,0)
        widget.setLayout(layout)
        self.tableWidgetCommands.setCellWidget(row, 0, widget)

        # Cột 1: Command
        item_name = QTableWidgetItem(name)
        item_name.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        self.tableWidgetCommands.setItem(row, 1, item_name)

        # Cột 2: Expected
        item_expected = QTableWidgetItem(str(expected))
        item_expected.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        self.tableWidgetCommands.setItem(row, 2, item_expected)

        # Cột 3: Value (Hex)
        item_value = QTableWidgetItem(value)
        item_value.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        self.tableWidgetCommands.setItem(row, 3, item_value)

    def load_xml_file(self, xml_path):
        # import xml.etree.ElementTree as ET
        tree = ET.parse(xml_path)
        root = tree.getroot()
        structs = []
        for struct in root.findall("Struct"):
            name_command = struct.attrib.get("name_command")
            command_id = struct.attrib.get("command_id")
            length = struct.attrib.get("len")
            payload = struct.attrib.get("payload")
            crc = struct.attrib.get("crc")
            structs.append({
                "name_command": name_command,
                "command_id": command_id,
                "len": length,
                "payload": payload,
                "crc": crc
            })

        # Đọc command list
        commands = []
        for cmd in root.find("CommandList").findall("Command"):
            name = cmd.find("Name").text
            value = cmd.find("Value").text
            expected = cmd.find("Expected").text
            commands.append((name, value, expected))
        self.tableWidgetCommands.setRowCount(len(commands))

        self.tableWidgetCommands.setRowCount(len(commands))
        for row, (name, value, expected) in enumerate(commands):
            self.add_row(name, value, expected, row)

    def load_xml_commands(self):

        settings = QSettings("QACompany", "SerialCommandTester")
        last_path = settings.value("LastXMLPath", "")
        fname, _ = QFileDialog.getOpenFileName(
            self, "Open XML File", last_path or "", "XML Files (*.xml)"
        )
        if not fname:
            return
        settings.setValue("LastXMLPath", fname)
        self.load_xml_file(fname)

        # fname, _ = QFileDialog.getOpenFileName(self, "Open XML File", "", "XML Files (*.xml)")
        # if not fname:
        #     return



        # tree = ET.parse(fname)
        # root = tree.getroot()
           
    def connect_serial(self):
        port = self.COMPort.currentText()
        baudrate = int(self.Baudrate.currentText())
        bytesize = int(self.NData.currentText())
        parity_str = self.Parity.currentText()
        stopbits_str = self.StopBit.currentText()
        # Quy đổi parity và stopbits cho pyserial
        parity_map = {
            "N": serial.PARITY_NONE,
            "E": serial.PARITY_EVEN,
            "O": serial.PARITY_ODD,
            "M": serial.PARITY_MARK,
            "S": serial.PARITY_SPACE,
        }
        stopbits_map = {
            "1": serial.STOPBITS_ONE,
            "1.5": serial.STOPBITS_ONE_POINT_FIVE,
            "2": serial.STOPBITS_TWO,
        }
        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity_map.get(parity_str, serial.PARITY_NONE),
                stopbits=stopbits_map.get(stopbits_str, serial.STOPBITS_ONE),
                timeout=0.1   # nhỏ hơn 1s để thread check liên tục
            )
            self.textEditLog.append(f"Connected to {port} OK.")
            # Start thread receive
            self._receiving = True
            self.receive_thread = threading.Thread(target=self.receive_serial, daemon=True)
            self.receive_thread.start()
        except Exception as e:
            self.textEditLog.append(f"Connect failed: {e}")

    def setup_table_columns(self):
        header = self.tableWidgetCommands.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.tableWidgetCommands.setColumnWidth(0, 60)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.tableWidgetCommands.setColumnWidth(0, 60)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.tableWidgetCommands.setColumnWidth(1, 120)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)

    def test_command(self):
        if self.Loop.isChecked():
            count = self.tableWidgetCommands.rowCount()
            for row in range(count):
                cell_widget = self.tableWidgetCommands.cellWidget(row, 0)
                if cell_widget:
                    checkbox = cell_widget.findChild(QCheckBox)
                    if checkbox and checkbox.isChecked():
                        value_item = self.tableWidgetCommands.item(row, 3)
                        if value_item:
                            hex_string = value_item.text()
                            self.send_command(hex_string)
        else:
            self.textEditLog.append("In Single mode, please select a command to test.")

    def send_command(self, hex_string):
        # Ví dụ: chuyển chuỗi "05 06 00 00 19" thành bytes và gửi qua serial
        try:
            # Lấy serial_port từ self.serial_port (đã connect trước đó)
            if not hasattr(self, "serial_port") or self.serial_port is None or not self.serial_port.is_open:
                self.textEditLog.append("Serial port disconnected!")
                return
            # Xử lý chuỗi hex thành bytes
            hex_str = hex_string.strip().replace(" ", "")
            data = bytes.fromhex(hex_str)
            self.serial_port.write(data)
            # Log: gửi đi hiện màu xanh dương
            self.append_log(f"Send: {hex_string}", "blue")
        except Exception as e:
            self.textEditLog.append(f"Error send: {e}")

    def append_log(self, text, color=None):
        # Nếu Timestamp được chọn, thêm giờ vào đầu dòng log
        if self.Timestamp.isChecked():
            now = datetime.now().strftime("[%H:%M:%S] ")
            text = now + text
        if color:
            self.textEditLog.setTextColor(Qt.GlobalColor.blue if color == "blue" else Qt.GlobalColor.red)
        self.textEditLog.append(text)
        self.textEditLog.setTextColor(Qt.GlobalColor.black)

    def receive_serial(self):
        while self._receiving and self.serial_port and self.serial_port.is_open:
            try:
                data = self.serial_port.read(1024)  # đọc tối đa 1024 bytes mỗi lần
                if data:
                    self.serial_receiver.data_received.emit(data)
            except Exception:
                pass
            time.sleep(0.01)  # tránh chiếm CPU

    def on_table_cell_clicked(self, row, col):
        # Nếu click vào cột 0 (Test) thì đảo trạng thái checkbox
        if col == 0:
            cell_widget = self.tableWidgetCommands.cellWidget(row, 0)
            if cell_widget:
                checkbox = cell_widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(not checkbox.isChecked())
        # Nếu ở chế độ Single và click vào cột 1 (Command), gửi lệnh luôn
        elif col == 1 and self.Single.isChecked():
            value_item = self.tableWidgetCommands.item(row, 3)
            if value_item:
                hex_string = value_item.text()
                self.send_command(hex_string)

    def on_serial_data_received(self, data):
        # Chuyển bytes thành chuỗi hex
        hex_str = ' '.join(f"{b:02X}" for b in data)
        self.append_log(f"{hex_str}", color="red")

    def clear_log(self):
        self.textEditLog.clear()

    def load_config(self):
        settings = QSettings("QACompany", "SerialCommandTester")
        port = settings.value("COMPort", "")
        baud = settings.value("Baudrate", "")
        parity = settings.value("Parity", "")
        stop = settings.value("StopBit", "")
        ndata = settings.value("NData", "")

        # Tự động chọn lại trên comboBox nếu giá trị tồn tại trong danh sách
        if port and port in [self.COMPort.itemText(i) for i in range(self.COMPort.count())]:
            self.COMPort.setCurrentText(port)
        if baud and baud in [self.Baudrate.itemText(i) for i in range(self.Baudrate.count())]:
            self.Baudrate.setCurrentText(baud)
        if parity and parity in [self.Parity.itemText(i) for i in range(self.Parity.count())]:
            self.Parity.setCurrentText(parity)
        if stop and stop in [self.StopBit.itemText(i) for i in range(self.StopBit.count())]:
            self.StopBit.setCurrentText(stop)
        if ndata and ndata in [self.NData.itemText(i) for i in range(self.NData.count())]:
            self.NData.setCurrentText(ndata)

        last_xml = settings.value("LastXMLPath", "")
        if last_xml and os.path.exists(last_xml):
            self.load_xml_file(last_xml)

    def save_config(self):
        settings = QSettings("QACompany", "SerialCommandTester")
        settings.setValue("COMPort", self.COMPort.currentText())
        settings.setValue("Baudrate", self.Baudrate.currentText())
        settings.setValue("Parity", self.Parity.currentText())
        settings.setValue("StopBit", self.StopBit.currentText())
        settings.setValue("NData", self.NData.currentText())


    def closeEvent(self, event):
        self.save_config()
        self._receiving = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        event.accept()



if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())