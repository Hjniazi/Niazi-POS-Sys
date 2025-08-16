# NiaziPOS - Point of Sale Application

NiaziPOS is a feature-rich desktop Point of Sale (POS) application built with Python and PyQt5. It provides a comprehensive set of tools for managing sales, inventory, products, and customers, making it suitable for small to medium-sized retail businesses.

## Features

- **User Authentication**: Secure login system with roles for administrators and cashiers.
- **Sales Processing**: An intuitive interface for processing sales, calculating totals, and handling payments.
- **Product Management**: Easily add, edit, and delete products with details like barcode, pricing, and stock levels.
- **Inventory Control**: Real-time stock tracking, with alerts for low stock levels.
- **Purchase Management**: Record purchases and update stock quantities accordingly.
- **Supplier Management**: Maintain a database of suppliers and track purchases from each.
- **Sales Analytics**: View sales history and generate reports to gain insights into your business performance.
- **PDF Receipts**: Generate and save PDF receipts for sales transactions.
- **Settings**: Customizable application settings for store name, tax rates, and more.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

- Python 3.x
- `pip` (Python package installer)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Install the required packages:**
   ```bash
   pip install PyQt5 fpdf2
   ```

## Running the Application

To run the application, execute the `main.py` script from the root directory:

```bash
python main.py
```

The application will start, and the database file `store.db` will be created automatically in the root directory if it doesn't exist.

### Default Login

A default administrator account is created the first time you run the application:

- **Username:** `admin`
- **Password:** `admin123`

You can use these credentials to log in and access the admin panel to manage users, products, and settings.

## Project Structure

The project is organized into the following directories:

- `assets/`: Contains static assets like icons and logos.
- `config/`: Application configuration, including styles and settings.
- `database/`: Handles database connection, schema (`schema.sql`), and data access logic.
- `reports/`: Contains the logic for generating PDF reports and receipts.
- `ui/`: All user interface components, including windows, dialogs, and custom widgets.

## Dependencies

- [PyQt5](https://pypi.org/project/PyQt5/): A comprehensive set of Python bindings for Qt v5.
- [fpdf2](https://pypi.org/project/fpdf2/): A library for PDF document generation.
