"""
config/style.py
Central stylesheet for the application (QSS).
Updated color palette and spacing for improved UX.
Buttons with property class="threeD" get the special 3D gradient style.
"""
def load_app_style():
    qss = """
    /* Palette & base */
    QWidget { font-family: "Segoe UI", Arial, sans-serif; font-size: 13px; color: #222; background: #f7f9fc; }
    QMainWindow, QWidget#mainWindow { background: #f7f9fc; }

    /* Inputs */
    QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QTextEdit {
        padding: 8px;
        border: 1px solid #d1d7de;
        border-radius: 8px;
        background: #ffffff;
    }

    QTableWidget {
        gridline-color: #e9eef5;
        background: #fff;
        alternate-background-color: #fbfdff;
    }

    QHeaderView::section {
        background: #f2f6fb;
        padding: 8px;
        border: 1px solid #e6eef9;
        font-weight: 700;
    }

    QGroupBox { font-weight: 700; margin-top: 10px; }

    /* 3D / Popup style button */
    QPushButton[class="threeD"] {
        border: 0;
        border-radius: 12px;
        padding: 12px 18px;
        font-size: 14px;
        font-weight: 700;
        min-width: 160px;
        min-height: 64px;
        color: #ffffff;
        text-align: left;
        qproperty-iconSize: 28px 28px;
        /* gradient background */
        background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
            stop:0 #58a6ff, stop:0.5 #3a89ff, stop:1 #1476ff);
    }

    /* When icons present, give text some left padding so icon + text don't overlap */
    QPushButton[class="threeD"]::menu-indicator { subcontrol-origin: padding; }
    QPushButton[class="threeD"] > QLabel { padding-left: 8px; }

    QPushButton[class="threeD"]:hover {
        background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
            stop:0 #70b9ff, stop:0.5 #58a6ff, stop:1 #2b9bff);
    }

    QPushButton[class="threeD"]:pressed {
        background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
            stop:0 #2f86d7, stop:0.5 #1f72c2, stop:1 #0e5aa3);
        padding-top: 14px;
    }

    /* smaller default buttons */
    QPushButton { border-radius: 8px; padding: 6px 10px; background: #fff; border: 1px solid #e0e6ef; }

    /* Header */
    QLabel#appHeader {
        font-size: 20px;
        font-weight: 800;
        color: #12417a;
    }

    /* Helpful spacing in dialogs */
    QDialog QPushButton { min-width: 88px; min-height: 30px; }

    """
    return qss
