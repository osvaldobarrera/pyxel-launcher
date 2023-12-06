import pyxel
import pyxel.cli as Pycli
from pathlib import Path
import os
import shutil
import sys
import zipfile
import glob
import inspect

THIS_DIR = Path( __file__ ).parent.absolute()
APPS_DIR = str((THIS_DIR / 'pyxel_examples/').resolve())
IS_STARTING = True

filearr = []
for root_dir, cur_dir, files in os.walk(APPS_DIR):
    for file in files:
        if file.endswith(('.pyxapp','.py')):
            filearr.append(file)
    break #only depth = 0
APPS = filearr

class Launcher:
    def __init__(self):
        global IS_STARTING
        if IS_STARTING:
            pyxel.init(200, 150, title="Pyxel Launcher")
            IS_STARTING = False

        self.games=APPS
        self.selector=0
        self.mainClass = Launcher
        self.tmpDir = ''
        pyxel.stop()
        pyxel.run(self.update, self.draw)

    def run(self):
        pyxel.stop()
        pyxel.run(self.update, self.draw)

    def update(self):
        if pyxel.btnp(pyxel.KEY_Q):
            pyxel.quit()
        if pyxel.btnp(pyxel.KEY_DOWN):
            self.selector=(self.selector+1)%len(self.games)
        if pyxel.btnp(pyxel.KEY_UP):
            self.selector=(self.selector-1)%len(self.games)
        if pyxel.btnp(pyxel.KEY_RETURN):
            if self.games[self.selector].endswith('.pyxapp'):
                self.select_pyxapp(self.games[self.selector])
            else:
                self.select_py()

    def draw(self):
        pyxel.cls(12)
        for i,g in enumerate(self.games):
            if i < 9:
                pyxel.text(3, 22 + (4*i)+(10*i), g, self.selector_color(i))
            else:
                pyxel.text(112, 22 + (4*(i-9))+(10*(i-9)), g, self.selector_color(i))
        pyxel.text(60, 1, "==LAUNCHER TEST==", 8)
        pyxel.text(25, 7, "('Enter' to select. 'M' to return)", 4)

    def selector_color(self, number):
        if (self.selector == number):
            return 2
        else:
            return 1

    def select_py(self):
        filename = self.games[self.selector]
        self.runfile(filename)

    def select_pyxapp(self, filename):
        file_path = str((Path(APPS_DIR) / filename).resolve())
        startup_script_file, self.tmpDir = launcherUtils._extract_pyxel_app(file_path)
        os.chdir(self.tmpDir)
        sys.path.append(str(Path(startup_script_file).parent.absolute()))
        self.runfile(startup_script_file)

    
    def runfile(self,filename):
        tmpDir = self.tmpDir
        code, mainClassName = launcherUtils.load_script(filename)
        print(code) #print modified code which will run
        exec(code, globals())

        # Injecting run function 
        def runPyxelApp(_self_):
            pyxel.run(_self_.update, _self_.draw)
        exec(mainClassName + '.runPyxelApp = runPyxelApp', globals(), locals())

        # Get the main class from the script 
        def getClass(self, targetClass):
            exec('self.mainClass = ' + mainClassName, globals(), locals())
        getClass(self, mainClassName)

        # Injectable update function
        def super_update(_self_):
            if pyxel.btnp(pyxel.KEY_M):
                if self.tmpDir != '':
                    shutil.rmtree(self.tmpDir)
                    launcherUtils.clear_local_imports(self.tmpDir)
                    self.tmpDir = ''
                    #sys.modules.clear()
                    sys.path.pop()
                exec(mainClassName + '= None', globals(),locals())
                self.mainClass = self
                self.run()

        # Injecting update function
        if hasattr(self.mainClass, 'update'):
            sub_update = self.mainClass.update
        def updateOverwritten(_self_):
            super_update(_self_)
            if hasattr(self.mainClass, 'update'):
                sub_update(_self_)
        self.mainClass.update = updateOverwritten

        #Creating instance of mainClass containing pyxel.run method
        app = self.mainClass()
        app.runPyxelApp()

class launcherUtils:
    # Parses and adapt the scripts in order to make them runnable. It mainly avoids to create more than one EventPump instance 
    def load_script(filename):
        print("")
        file_path = str((Path(APPS_DIR) / filename).resolve())
        print(file_path)
        mainClass = ""
        with open(file_path, 'r') as file:
            code = file.read()
            codeLines = code.splitlines()
            searchingMainClass = True
            searchingParenthesis = False
            pyxelalias = 'pyxel'
            for i, line in enumerate(codeLines):
                if 'import pyxel as' in line:
                    pyxelalias = line.split()[-1]

                if searchingMainClass and ((''.join(line.split())).startswith('class')):
                    mainClass = line.split()[-1].replace(':','') #Use \t and \n as separator and remove colons(:)

                if pyxelalias+'.init(' in line:
                    if ')' not in line:
                        searchingParenthesis = True
                    codeLines[i] = line.replace(pyxelalias+'.init(', 'print()#'+pyxelalias+'.init(') #The empty print prevents the creation of empty functions
                    searchingMainClass = False

                if pyxelalias+'.run(' in line:
                    if ')' not in line:
                        searchingParenthesis = True
                    codeLines[i] = line.replace(pyxelalias+'.run(', 'print()#'+pyxelalias+'.run(')

                if searchingParenthesis == True:
                    if ')' in line:
                        searchingParenthesis = False
                    codeLines[i] = line.replace(line, '#'+line)              

            code = '\n'.join(codeLines)
            os.chdir(Path(file_path).parent.absolute())
            return code, mainClass
        return "",""

    # Slight modification of the original. This one retrieves the temp path for its deletion
    def _extract_pyxel_app(pyxel_app_file):
        pyxel_app_file = Pycli._complete_extension(pyxel_app_file, pyxel.APP_FILE_EXTENSION)
        Pycli._check_file_exists(pyxel_app_file)
        app_dir = Pycli._create_app_dir()
        zf = zipfile.ZipFile(pyxel_app_file)
        zf.extractall(app_dir)
        pattern = os.path.join(app_dir, "*", pyxel.APP_STARTUP_SCRIPT_FILE)
        for setting_file in glob.glob(pattern):
            with open(setting_file, "r") as f:
                return os.path.join(os.path.dirname(setting_file), f.read()), app_dir
        return None, None

    # Prevevent name collisions between modules, like the ones between 30 Secs of Daylight and Megaball
    def clear_local_imports(path):
        modules = sys.modules
        toDelete = []
        for m in modules:
            try:
              if path in str(inspect.getfile(modules[m])):
                toDelete.append(m)
            except:
              '''Here be dragons'''
        for m in toDelete:
            del sys.modules[m]


Launcher()