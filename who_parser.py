import sys
import time
import traceback
import os
from configparser import ConfigParser
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PySide6.QtCore import QThread, Slot, Signal, QObject
from PySide6.QtWidgets import QApplication, QMainWindow, QPlainTextEdit, QVBoxLayout, QPushButton, QWidget, QFileDialog, QMessageBox


DIRECTORY = 'H:\Everquest\Logs'


class WorkerKilledException(Exception):
    pass


class WorkerSignals(QObject):

    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)


class Watcher:

    def __init__(self, response_function, directory):
        self.observer = Observer()
        self.response_function = response_function
        self.directory = directory

    def run(self):
        self.observer.schedule(self.response_function,
                               self.directory, recursive=False)
        self.observer.start()
        try:
            while self.observer.is_alive():
                self.observer.join(1)

        except:
            self.observer.stop()
            self.observer.join()
            return 0
        return 1

    def stop(self):
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
            return 1
        return 0


class Thread(QThread):
    """
    Worker thread
    """

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    @Slot()
    def run(self):
        """
        Initialize the runner function with passed args, kwargs.
        """
        # Retrieve args/kwargs here; and fire processing using them
        try:

            # watch directory
            result = self.fn(*self.args, **self.kwargs)

        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]


class Watch_Directory_Thread(Thread):

    def __init__(self, directory, signals=None, *args, **kwargs):
        if not signals:
            raise ValueError('signals must be passed')
        super().__init__(self.watch_directory, signals=signals, *args, **kwargs)
        self.directory = directory

    def watch_directory(self, signals=None):
        self.watcher = Watcher(FileOnModifiedHandler(signals), self.directory)
        res = self.watcher.run()
        return res


class FileOnModifiedHandler(FileSystemEventHandler):

    def __init__(self, signals):
        self.signals = signals

    def on_modified(self, event):
        self.file_name = event.src_path.split('\\')[-1]
        # print(f'file modified: {self.file_name}')
        if self.signals and self.file_name != 'dbg.txt':
            self.signals.result.emit(self.file_name)
            # print(f'emitting file modified: {self.file_name}')


class File_Stream_Thread(Thread):

    def __init__(self, current_file, signals, *args, **kwargs):
        super().__init__(self.log_lines, signals=signals, *args, **kwargs)
        self.current_file = current_file
        self.directory = DIRECTORY

    def log_lines(self, signals):
        self.logfile = open(self.directory + '\\' + self.current_file, 'r')
        loglines = self.logtail(self.logfile)
        self.signals = signals

        for line in loglines:
            self.signals.result.emit(line)

    def logtail(self, logfile):
        thefile = logfile
        thefile.seek(0, 2)
        while True:
            line = thefile.readline()
            if not line:
                time.sleep(0.1)
                continue
            yield line


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # self.directory = DIRECTORY
        self.file = None
        self.setup_ui()
        self.show()
        
        self.directory = ''
        res = self.setup_config()
        if not res:
            sys.exit()
        self.start_watcher_directory()

    def setup_config(self):

        '''
        self.cwd = os.getcwd()
        self.config_exists = os.path.exists(self.cwd+"\parseconfig.ini")
        self.config = ConfigParser()
        self.config_file = 'parseconfig.ini'

        if self.config_exists:
            self.config.read(self.config_file)
            self.directory = self.config['default']['directory']
        else:
            button = QMessageBox.information(
                self,
                "Directory Not Selected",
                "Click Ok to select your EverQuest Log Directory",
                buttons=QMessageBox.Ok | QMessageBox.Cancel,
            )
            if button == QMessageBox.Ok:
                self.directory = QFileDialog.getExistingDirectory(
                    caption='Select your EverQuest Directory')
                if self.directory == "":
                    sys.exit()
                self.directory += '/Logs'
                if not os.path.exists(self.directory):
                    self.setup_config()
                self.config.add_section('default')
                self.config.set('default', 'directory', self.directory)
                with open(self.config_file, 'w') as configfile:
                    self.config.write(configfile)
            else:
                sys.exit()
        '''
        config = ConfigParser()
        config_file = 'config.ini'
        if os.path.exists(config_file):
            config.read(config_file)
            if config.has_option('default', 'directory'):
                self.directory = config['default']['directory']
                return config
        
        button = QMessageBox.information(
            self,
            "Directory Not Selected",
            "Click Ok to select your EverQuest Directory",
            buttons=QMessageBox.Ok | QMessageBox.Cancel,
        )
        if button != QMessageBox.Ok:
            return None
            
        self.directory = QFileDialog.getExistingDirectory(
            caption='Select your EverQuest Directory')
        if not self.directory:
            return None
        if '/Logs' not in self.directory:
            self.directory += '/Logs'
        if not os.path.exists(self.directory):
            self.setup_config()
        config.add_section('default')
        config.set('default', 'directory', self.directory)
        with open(config_file, 'w') as cf:
            config.write(cf)
        return config
            

    def setup_ui(self):
        self.setWindowTitle("Who Parser")
        widget = QWidget()
        layout = QVBoxLayout()
        self.editor = QPlainTextEdit()
        self.clear_button = QPushButton("Clear Text")
        self.clear_button.clicked.connect(self.clear_text)
        layout.addWidget(self.editor)
        layout.addWidget(self.clear_button)
        widget.setLayout(layout)
        self.setCentralWidget(widget)

    def start_watcher_directory(self):
        self.watch_directory_signals = WorkerSignals()
        self.watch_directory_signals.result.connect(self.file_compare)
        self.watch_directory_thread = Watch_Directory_Thread(
            self.directory, signals=self.watch_directory_signals)
        self.watch_directory_thread.start()

    def file_compare(self, file):
        if self.file != file:
            self.file = file
            self.start_file_stream(self.file)

    def set_text(self, line):
        new_line = line
        current_text = self.editor.toPlainText()
        updated_text = current_text + new_line
        self.editor.setPlainText(updated_text)

    def start_file_stream(self, new_file):
        self.file = new_file
        self.file_stream_signals = WorkerSignals()
        self.file_stream_signals.result.connect(self.set_text)
        self.file_stream_thread = File_Stream_Thread(
            self.file, self.file_stream_signals)
        self.file_stream_thread.start()

    def closeEvent(self, event):
        # events to trigger when app is closed out
        try:
            self.watch_directory_thread.terminate()
            self.file_stream_thread.terminate()

        except:
            print("no running threads")

    def clear_text(self):
        self.editor.setPlainText("")
        self.start_file_stream()


app = QApplication(sys.argv)
window = MainWindow()
sys.exit(app.exec())
