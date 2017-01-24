'''
Created on Jul 23, 2014

modified by Ed Barnard
ui enhancements by Alan Buckley
'''
from __future__ import print_function, division, absolute_import

import sys, os
import time
import datetime
import numpy as np
import collections
from collections import OrderedDict
import logging

try:
    import configparser
except: # python 2
    import ConfigParser as configparser


from qtpy import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
#import pyqtgraph.console

try:
    import IPython
    if IPython.version_info[0] < 4: #compatibility for IPython < 4.0 (pre Jupyter split)
        from IPython.qt.console.rich_ipython_widget import RichIPythonWidget as RichJupyterWidget
        from IPython.qt.inprocess import QtInProcessKernelManager
    else:
        from qtconsole.rich_jupyter_widget import RichJupyterWidget
        from qtconsole.inprocess import QtInProcessKernelManager
    CONSOLE_TYPE = 'qtconsole'
except Exception as err:
    logging.warning("ScopeFoundry unable to import iPython console, using pyqtgraph.console instead. Error: {}".format( err))
    import pyqtgraph.console
    CONSOLE_TYPE = 'pyqtgraph.console'
    
#import matplotlib
#matplotlib.rcParams['backend.qt4'] = 'PySide'
#from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
#from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar2

#from matplotlib.figure import Figure

from .logged_quantity import LoggedQuantity, LQCollection

from .helper_funcs import confirm_on_close, ignore_on_close, load_qt_ui_file, OrderedAttrDict, sibling_path, get_logger_from_class

#from equipment.image_display import ImageDisplay


import warnings
import traceback

# See https://riverbankcomputing.com/pipermail/pyqt/2016-March/037136.html
# makes sure that unhandled exceptions in slots don't crash the whole app with PyQt 5.5 and higher
# old version:
## sys.excepthook = traceback.print_exception
# new version to send to logger
def log_unhandled_exception(*exc_info):
    text = "".join(traceback.format_exception(*exc_info))
    logging.critical("Unhandled exception:" + text)
#sys.excepthook = log_unhandled_exception

class BaseApp(QtCore.QObject):
    
    def __init__(self, argv):
        QtCore.QObject.__init__(self)
        self.log = get_logger_from_class(self)
        
        self.this_dir, self.this_filename = os.path.split(__file__)

        self.qtapp = QtWidgets.QApplication.instance()
        if not self.qtapp:
            self.qtapp = QtWidgets.QApplication(argv)
        
        self.settings = LQCollection()
        
        self.setup_console_widget()
        # FIXME Breaks things for microscopes, but necessary for stand alone apps!
        #if hasattr(self, "setup"):
        #    self.setup() 

        if not hasattr(self, 'name'):
            self.name = "ScopeFoundry"
        self.qtapp.setApplicationName(self.name)

        
    def exec_(self):
        return self.qtapp.exec_()
        
    def setup_console_widget(self):
        # Console
        if CONSOLE_TYPE == 'pyqtgraph.console':
            self.console_widget = pyqtgraph.console.ConsoleWidget(namespace={'app':self, 'pg':pg, 'np':np}, text="ScopeFoundry Console")
        elif CONSOLE_TYPE == 'qtconsole':
            # https://github.com/ipython/ipython-in-depth/blob/master/examples/Embedding/inprocess_qtconsole.py
            self.kernel_manager = QtInProcessKernelManager()
            self.kernel_manager.start_kernel()
            self.kernel = self.kernel_manager.kernel
            self.kernel.gui = 'qt4'
            self.kernel.shell.push({'np': np, 'app': self})
            self.kernel_client = self.kernel_manager.client()
            self.kernel_client.start_channels()
    
            #self.console_widget = RichIPythonWidget()
            self.console_widget = RichJupyterWidget()
            self.console_widget.setWindowTitle("ScopeFoundry IPython Console")
            self.console_widget.kernel_manager = self.kernel_manager
            self.console_widget.kernel_client = self.kernel_client
        else:
            raise ValueError("CONSOLE_TYPE undefined")
        
        return self.console_widget         

    def setup(self):
        pass


    def settings_save_ini(self, fname, save_ro=True):
        config = configparser.ConfigParser()
        config.optionxform = str
        config.add_section('app')
        config.set('app', 'name', self.name)
        for lqname, lq in self.settings.as_dict().items():
            if not lq.ro or save_ro:
                config.set('app', lqname, lq.ini_string_value())
                
        with open(fname, 'wb') as configfile:
            config.write(configfile)
        
        self.log.info("ini settings saved to {} {}".format( fname, config.optionxform))    

    def settings_load_ini(self, fname):
        self.log.info("ini settings loading from " + fname)
        
        def str2bool(v):
            return v.lower() in ("yes", "true", "t", "1")

        config = configparser.ConfigParser()
        config.optionxform = str
        config.read(fname)

        if 'app' in config.sections():
            for lqname, new_val in config.items('app'):
                #print(lqname)
                lq = self.settings.as_dict().get(lqname)
                if lq:
                    if lq.dtype == bool:
                        new_val = str2bool(new_val)
                    lq.update_value(new_val)

    def settings_save_ini_ask(self, dir=None, save_ro=True):
        # TODO add default directory, etc
        fname, _ = QtWidgets.QFileDialog.getSaveFileName(self.ui, caption=u'Save Settings', dir=u"", filter=u"Settings (*.ini)")
        #print(repr(fname))
        if fname:
            self.settings_save_ini(fname, save_ro=save_ro)
        return fname

    def settings_load_ini_ask(self, dir=None):
        # TODO add default directory, etc
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(None, "Settings (*.ini)")
        #print(repr(fname))
        if fname:
            self.settings_load_ini(fname)
        return fname  

class BaseMicroscopeApp(BaseApp):
    name = "ScopeFoundry"
    mdi = True
    
    def __del__ ( self ): 
        self.ui = None

    def show(self): 
        #self.ui.exec_()
        self.ui.show()

    def __init__(self, argv):
        BaseApp.__init__(self, argv)
        
        if not hasattr(self, 'ui_filename'):
            if self.mdi:
                self.ui_filename = sibling_path(__file__,"base_microscope_app_mdi.ui")
            else:
                self.ui_filename = sibling_path(__file__,"base_microscope_app.ui")
        # Load Qt UI from .ui file
        self.ui = load_qt_ui_file(self.ui_filename)
        if self.mdi:
            self.ui.col_splitter.setStretchFactor(0,0)
            self.ui.col_splitter.setStretchFactor(1,1)
        
        self.hardware = OrderedAttrDict()
        self.measurements = OrderedAttrDict()

        self.quickbar = None
                   
        self.setup()
        
        self.setup_default_ui()

    def retrieveSelectionID(self):
        self.items = self.ui.measurements_treeWidget.selectedItems()
        for item in self.items:
            return(item.text(0))

    def openContextMenu(self, position):
#         indexes =  self.ui.measurements_treeWidget.selectedIndexes()
#         if len(indexes) > 0:
#             level = 0
#             index = indexes[0]
#             while index.parent().isValid():
#                 index = index.parent()
#                 level += 1
        menu = QtWidgets.QMenu()
#         if level == 0:
#             startAction = menu.addAction(self.tr("Start Measurement"))
#             interruptAction = menu.addAction(self.tr("Interrupt Measurement"))

        startAction = menu.addAction(self.tr("Start Measurement"))
        interruptAction = menu.addAction(self.tr("Interrupt Measurement"))
        
        action = menu.exec_(self.ui.measurements_treeWidget.viewport().mapToGlobal(position))
        if action == startAction:
            print('startAction')
            self.measurements['{}'.format(self.retrieveSelectionID())].start()
            #print('{}'.format(self.retrieveSelectionID()))
        elif action == interruptAction:
            print('interruptAction')
            self.measurements['{}'.format(self.retrieveSelectionID())].start()
            #print('{}'.format(self.retrieveSelectionID()))

    def setup_default_ui(self):
        
        confirm_on_close(self.ui, title="Close %s?" % self.name, message="Do you wish to shut down %s?" % self.name, func_on_close=self.on_close)
        
        self.ui.hardware_treeWidget.setColumnWidth(0,175)
        self.ui.measurements_treeWidget.setColumnWidth(0,175)

        self.ui.measurements_treeWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.ui.measurements_treeWidget.customContextMenuRequested.connect(self.openContextMenu) #(self.openContextMenu)

        # Setup the figures         
        for name, measure in self.measurements.items():
            self.log.info("setting up figures for {} measurement {}".format( name, measure.name) )            
            measure.setup_figure()
            if self.mdi and hasattr(measure, 'ui'):
                measure.subwin = self.ui.mdiArea.addSubWindow(measure.ui, QtCore.Qt.CustomizeWindowHint | QtCore.Qt.WindowMinMaxButtonsHint)
                ignore_on_close(measure.subwin)
                #measure.subwin.installEventFilter()
                #measure.ui.setWindowFlags()
                measure.ui.show()            
        
        if hasattr(self.ui, 'console_pushButton'):
            self.ui.console_pushButton.clicked.connect(self.console_widget.show)
            self.ui.console_pushButton.clicked.connect(self.console_widget.activateWindow)
                        
        if self.quickbar is None:
            # Collapse sidebar
            self.ui.quickaccess_scrollArea.setVisible(False)
            pass
        
        
        
        
        #settings events
        if hasattr(self.ui, "settings_autosave_pushButton"):
            self.ui.settings_autosave_pushButton.clicked.connect(self.settings_auto_save)
        if hasattr(self.ui, "settings_load_last_pushButton"):
            self.ui.settings_load_last_pushButton.clicked.connect(self.settings_load_last)
        if hasattr(self.ui, "settings_save_pushButton"):
            self.ui.settings_save_pushButton.clicked.connect(self.settings_save_dialog)
        if hasattr(self.ui, "settings_load_pushButton"):
            self.ui.settings_load_pushButton.clicked.connect(self.settings_load_dialog)
        
        #Menu bar entries:
        # To do: connect self.ui.action_set_data_dir to save data directory function 
            # (Function has yet to be created)
        # To do: connect self.ui.action_log_viewer to log viewer function
            # (Function has yet to be created)
        self.ui.action_load_ini.triggered.connect(self.settings_load_dialog)
        self.ui.action_save_ini.triggered.connect(self.settings_save_dialog)
        self.ui.action_console.triggered.connect(self.console_widget.show)
        self.ui.action_console.triggered.connect(self.console_widget.activateWindow)
        
        
        #Refer to existing ui object:
        self.menubar = self.ui.menuWindow

        #Create new action group: 
        self.action_group = QtWidgets.QActionGroup(self)
        
        #Generate actions:
        #self.windowAction = QtWidgets.QAction("Sub&window Mode", self, checkable=True, shortcut="Alt+W")
        #self.tabAction = QtWidgets.QAction("&Tab Mode", self, checkable=True, shortcut="Alt+T")       
        
        #Add actions to group:
        self.action_group.addAction(self.ui.windowAction)
        self.action_group.addAction(self.ui.tabAction)
        
        #Add actions to "Window Menu Bar"
        #self.menubar.addAction(self.windowAction)
        #self.menubar.addAction(self.tabAction)
        
        self.ui.mdiArea.setTabsClosable(False)
        self.ui.mdiArea.setTabsMovable(True)
        
        
        self.ui.tabAction.triggered.connect(self.set_tab_mode)
        self.ui.windowAction.triggered.connect(self.set_subwindow_mode)
        self.ui.actionCascade.triggered.connect(self.cascade_layout)
        self.ui.actionTile.triggered.connect(self.tile_layout)
            
    def set_subwindow_mode(self):
        self.ui.mdiArea.setViewMode(self.ui.mdiArea.SubWindowView)
    
    def set_tab_mode(self):
        self.ui.mdiArea.setViewMode(self.ui.mdiArea.TabbedView)
        
    def cascade_layout(self):
        self.ui.mdiArea.tileSubWindows()
        
    def tile_layout(self):
        self.ui.mdiArea.cascadeSubWindows()
    
    def add_quickbar(self, widget):
        self.ui.quickaccess_scrollArea.setVisible(True)
        self.ui.quickaccess_scrollAreaWidgetContents.layout().addWidget(widget)
        self.quickbar = widget
        return self.quickbar
        
    def on_close(self):
        self.log.info("on_close")
        # disconnect all hardware objects
        for hw in self.hardware.values():
            self.log.info("disconnecting {}".format( hw.name))
            if hw.settings['connected']:
                try:
                    hw.disconnect()
                except Exception as err:
                    self.log.error("tried to disconnect {}: {}".format( hw.name, err) )

    def setup(self):
        """ Override to add Hardware and Measurement Components"""
        #raise NotImplementedError()
        pass
    
        
    """def add_image_display(self,name,widget):
        print "---adding figure", name, widget
        if name in self.figs:
            return self.figs[name]
        else:
            disp=ImageDisplay(name,widget)
            self.figs[name]=disp
            return disp
    """
        
    def add_pg_graphics_layout(self, name, widget):
        self.log.info("---adding pg GraphicsLayout figure {} {}".format( name, widget))
        if name in self.figs:
            return self.figs[name]
        else:
            disp=pg.GraphicsLayoutWidget(border=(100,100,100))
            widget.layout().addWidget(disp)
            self.figs[name]=disp
            return disp
        
        # IDEA: write an abstract function to add pg.imageItem() for maps, 
        # which haddels, pixelscale, ROI ....
        # could also be implemented in the base_2d class? 
            
            
    
#     def add_figure_mpl(self,name, widget):
#         """creates a matplotlib figure attaches it to the qwidget specified
#         (widget needs to have a layout set (preferably verticalLayout) 
#         adds a figure to self.figs"""
#         print "---adding figure", name, widget
#         if name in self.figs:
#             return self.figs[name]
#         else:
#             fig = Figure()
#             fig.patch.set_facecolor('w')
#             canvas = FigureCanvas(fig)
#             nav    = NavigationToolbar2(canvas, self.ui)
#             widget.layout().addWidget(canvas)
#             widget.layout().addWidget(nav)
#             canvas.setFocusPolicy( QtCore.Qt.ClickFocus )
#             canvas.setFocus()
#             self.figs[name] = fig
#             return fig
    
    def add_figure(self,name,widget):
        return self.add_figure_mpl(name,widget)
    

    def add_hardware_component(self,hc):
        self.hardware.add(hc.name, hc)
        return hc
    
    def add_measurement_component(self, measure):
        assert not measure.name in self.measurements.keys()
        self.measurements.add(measure.name, measure)

        return measure
    
    def settings_save_h5(self, fname):
        from . import h5_io
        with h5_io.h5_base_file(self, fname) as h5_file:
            for measurement in self.measurements.values():
                h5_io.h5_create_measurement_group(measurement, h5_file)
            self.log.info("settings saved to {}".format(h5_file.filename))
            
    def settings_save_ini(self, fname, save_ro=True, save_gui=True, save_hardware=True, save_measurements=True):
        config = configparser.ConfigParser()
        config.optionxform = str
        if save_gui:
            config.add_section('app')
            for lqname, lq in self.settings.items():
                config.set('app', lqname, lq.val)
        if save_hardware:
            for hc_name, hc in self.hardware.items():
                section_name = 'hardware/'+hc_name            
                config.add_section(section_name)
                for lqname, lq in hc.settings.items():
                    if not lq.ro or save_ro:
                        config.set(section_name, lqname, lq.val)
        if save_measurements:
            for meas_name, measurement in self.measurements.items():
                section_name = 'measurement/'+meas_name            
                config.add_section(section_name)
                for lqname, lq in measurement.settings.items():
                    if not lq.ro or save_ro:
                        config.set(section_name, lqname, lq.val)
        with open(fname, 'wb') as configfile:
            config.write(configfile)
        
        self.log.info("ini settings saved to {} {}".format( fname, config.optionxform))


        
    def settings_load_ini(self, fname):
        self.log.info("ini settings loading from {}".format(fname))
        
        def str2bool(v):
            return v.lower() in ("yes", "true", "t", "1")


        config = configparser.ConfigParser()
        config.optionxform = str
        config.read(fname)

        if 'app' in config.sections():
            for lqname, new_val in config.items('app'):
                lq = self.settings[lqname]
                if lq.dtype == bool:
                    new_val = str2bool(new_val)
                lq.update_value(new_val)
        
        for hc_name, hc in self.hardware.items():
            section_name = 'hardware/'+hc_name
            self.log.info(section_name)
            if section_name in config.sections():
                for lqname, new_val in config.items(section_name):
                    try:
                        lq = hc.settings.get_lq(lqname)
                        if lq.dtype == bool:
                            new_val = str2bool(new_val)
                        if not lq.ro:
                            lq.update_value(new_val)
                    except Exception as err:
                        self.log.error("-->Failed to load config for {}/{}, new val {}: {}".format(section_name, lqname, new_val, repr(err)))
                        
        for meas_name, measurement in self.measurements.items():
            section_name = 'measurement/'+meas_name            
            if section_name in config.sections():
                for lqname, new_val in config.items(section_name):
                    lq = measurement.settings.get_lq(lqname)
                    if lq.dtype == bool:
                        new_val = str2bool(new_val)                    
                    if not lq.ro:
                        lq.update_value(new_val)
        
        self.log.info("ini settings loaded from {}"+ fname)
        
    def settings_load_h5(self, fname):
        import h5py
        with h5py.File(fname) as h5_file:
            pass
    
    def settings_auto_save(self):
        #fname = "%i_settings.h5" % time.time()
        #self.settings_save_h5(fname)
        self.settings_save_ini("%i_settings.ini" % time.time())

    def settings_load_last(self):
        import glob
        #fname = sorted(glob.glob("*_settings.h5"))[-1]
        #self.settings_load_h5(fname)
        fname = sorted(glob.glob("*_settings.ini"))[-1]
        self.settings_load_ini(fname)
    
    
    def settings_save_dialog(self):
        fname, selectedFilter = QtWidgets.QFileDialog.getSaveFileName(self.ui, "Save Settings file", "", "Settings File (*.ini)")
        if fname:
            self.settings_save_ini(fname)
    
    def settings_load_dialog(self):
        fname, selectedFilter = QtWidgets.QFileDialog.getOpenFileName(self.ui,"Open Settings file", "", "Settings File (*.ini *.h5)")
        self.settings_load_ini(fname)

    @property
    def hardware_components(self):
        warnings.warn("App.hardware_components deprecated, used App.hardware", DeprecationWarning)
        return self.hardware
    @property
    def measurement_components(self):
        warnings.warn("App.measurement_components deprecated, used App.measurements", DeprecationWarning)
        return self.measurements
    @property
    def logged_quantities(self):
        warnings.warn('app.logged_quantities deprecated use app.settings', DeprecationWarning)
        return self.settings.as_dict()

if __name__ == '__main__':
    
    app = BaseMicroscopeApp(sys.argv)
    
    sys.exit(app.exec_())