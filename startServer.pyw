print("Loading...")
import tornado.ioloop
import tornado.web
import tornado.websocket
import socket
import os
import json
import ctypes
import psutil
import base64
import pyautogui
import threading
import io
import cv2
import PIL
import string
import random # Used for generating random tokens
import time
import traceback
import datetime
import shutil
import sys
import signal
import requests
from hurry.filesize import size as toString_filesize

# Local Imports
from balloontip import toast
user32 = ctypes.windll.user32

THREADSSTOP = False

MUSICPATH = "C:\\Users\\ezhao\\Music\\\"Illenium - Awake (Full Album).mp3\""
UPDATEURL = "https://raw.githubusercontent.com/Wha-The/RemoteConfiguration/main/startServer.pyw"
def generate_new_resource_token():
	open("./RESOURCE_TOKEN.txt",'w').write(''.join([random.choice(string.letters) for i in range(300)]))
	open("./FTP_RESOURCE_TOKEN.txt",'w').write(''.join([random.choice(string.letters) for i in range(300)]))
def GetPid(appName):
# Get a list of all running processes
	list = psutil.pids()

	# Go though list and check each processes executeable name for XXX
	for i in range(0, len(list)):
		try:
			p = psutil.Process(list[i])
			if p.cmdline()[0].lower().find(appName.lower()) != -1 and p.pid!=os.getpid():
				return p.name(),p.cmdline()[0],p.pid
		except:
			pass
	return None,None,None

def get_size(start_path = '.'):
    total_size = 0
    if os.path.isfile(start_path):
    	return os.path.getsize(start_path)
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # skip if it is symbolic link
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)

    return total_size
def BackgroundProcess():
	return not sys.stdout.isatty()

class Templates_template():
	def __init__(self):
		self.BasePath = "./templates/"
	def __getattr__(self,attr):
		filename = os.path.join(self.BasePath,attr+".html")
		return filename

Templates = Templates_template()
del Templates_template
ws_connections = {"screenshot":set(),"camera":set(),"logs":set()}

class BaseHandler(tornado.web.RequestHandler):
	def read(self,fname):return open(fname,'r').read()
	def checkAuthenticated(self,redirect=True):
		resource_token = self.get_secure_cookie("Load_Resource_Token")
		if resource_token != open("./RESOURCE_TOKEN.txt").read():
			if redirect:
				self.redirect("/")
			return False
		return True
	def FTP_checkAuthenticated(self,redirect=True):
		resource_token = self.get_secure_cookie("FTP_Resource_Token")
		if resource_token != open("./FTP_RESOURCE_TOKEN.txt").read():
			if redirect:
				self.redirect("/ftp_login")
			return False
		return True
	def logAction(self,action):
		addedlog = {"user":"Anonymous","time":str(datetime.datetime.now()),"action":action}
		logs = json.loads(open("Logs.txt",'r').read())
		logs.append(addedlog)
		open("Logs.txt",'w').write(json.dumps(logs))
		[client.write_message(json.dumps({"content-type":"Type:LogUpdate","content":addedlog})) for client in ws_connections["logs"]]
class MainHandler(BaseHandler):
	def get(self):
		if self.checkAuthenticated(redirect=False):
			self.redirect("/control")
			return
		self.render(Templates.login)
	def post(self):
		currentpassword = open("./Password.txt","r").read()
		password = self.get_argument("password","")
		if currentpassword != password:
			self.write({"error":"Incorrect password"})
			return
		self.logAction("Log in")
		self.set_secure_cookie("Load_Resource_Token",open("./RESOURCE_TOKEN.txt").read())
		self.write({"content":"/control"})
class ControlHandler(BaseHandler):
	def get(self):
		if not self.checkAuthenticated():return
		self.render(Templates.control)
	def post(self):
		if not self.checkAuthenticated(redirect=False):
			self.write({"error":"Not logged in or log in token expired. Please log out and sign in again"})
			return
		action = self.get_argument("action","")
		try:
			data = json.loads(self.get_argument("data","{}"))
		except:
			self.set_status(400)
			self.write({"error":"Bad Request"})
			return
		if action == "lock":
			user32.LockWorkStation()
			self.write({"content":"Locked PC"})
		elif action == "terminateProgram" or action == "suspendProgram" or action == "resumeProgram":
			pname = data["name"]
			result = GetPid(pname)
			if result[2]:
				actionname = {"terminateProgram":"terminate","suspendProgram":"suspend","resumeProgram":"resume"}[action]
				try:
					proc = psutil.Process(result[2])
					f = getattr(proc,actionname)
					f()
				except Exception as e:
					self.write({"error":"psutil error: "+str(e)})
					return
				self.write({"content":actionname.capitalize()+(actionname[-1]!="e" and "e" or "")+"d Program(Name=%s, PID=%s)"%(result[0],str(result[2]))})
			else:
				self.write({"error":"No such program"})
		elif action == "takeScreenshot":
			screenshot = pyautogui.screenshot()
			buffer = io.BytesIO()
			screenshot.save(buffer,format="JPEG")
			bytes = buffer.getvalue()
			self.write({"content":base64.b64encode(bytes),"scale":25,"content-type":"img:base64"})
			toast("Screenshot taken","A take screenshot request was sent from the RemoteConfiguration localhost")
		elif action == "takeCameraPicture":
			vc = cv2.VideoCapture(1)
			success, frame = vc.read()
			del vc
			if not success:
				self.write({"error":"Camera failed to take picture"})
				return
			img = PIL.Image.fromarray(frame)
			buffer = io.BytesIO()
			img.save(buffer,format="JPEG")
			bytes = buffer.getvalue()
			self.write({"content":base64.b64encode(bytes),"scale":25,"content-type":"img:base64"})
			toast("Picture taken","A take picture from camera request was sent from the RemoteConfiguration localhost")
		elif action == "runcmd":
			os.system(data["cmd"])
		elif action == "playMusic":
			os.system("start "+MUSICPATH)
			self.write({"content":"Started music "+os.path.split(MUSICPATH)[1]})
		else:
			self.write({"content":"Action not found (Client error)"})
		self.logAction("Request; action:%s, data: %s"%(action,json.dumps(data)))

class LogsWebSocketHandler(tornado.websocket.WebSocketHandler):
	def open(self):
		resource_token = self.get_secure_cookie("Load_Resource_Token")
		if resource_token != open("./RESOURCE_TOKEN.txt").read():
			self.close()
			return
		ws_connections["logs"].add(self)
	def on_message(self, message):
		resource_token = self.get_secure_cookie("Load_Resource_Token")
		if resource_token != open("./RESOURCE_TOKEN.txt").read():
			self.close()
			return
		try:
			message = json.loads(message)
		except:
			self.write_message(json.dumps({"error":"400 Bad Request"}))
			return
		action = message["action"]
		data = message.get("data")
		if action == "GetLogs":
			logs = json.loads(open("./Logs.txt",'r').read())
			start = (data["start"]>0 and data["start"] or 0)
			end = (data["end"]<=len(logs) and data["end"]>start and data["end"] or len(logs))
			logs.reverse()
			reversedlogs = list(logs[start:end])
			self.write_message(json.dumps({"content-type":"Type:LogsFetched","content":reversedlogs,"index":[start,end]}))
	def on_close(self):
		ws_connections["logs"].remove(self)




class LiveWebSocketHandler(tornado.websocket.WebSocketHandler):
	def open(self):
		resource_token = self.get_secure_cookie("Load_Resource_Token")
		if resource_token != open("./RESOURCE_TOKEN.txt").read():
			self.close()
			return

	def on_message(self, message):
		try:
			message = json.loads(message)
		except:
			self.write_message(json.dumps({"error":"400 Bad Request"}))
		resource_token = self.get_secure_cookie("Load_Resource_Token")
		if resource_token != open("./RESOURCE_TOKEN.txt").read():
			self.close()
			return
		feed = message["feed"] # Get what the client is listening for
		reconnection=message["reconnection"]
		showtoast = (reconnection and (lambda title,body:None) or toast)
		success = True
		if feed == "screenshot":
			showtoast("Live Screenshot Feed Started","Live Screenshot Feed started for a client")
			ws_connections["screenshot"].add(self)
		elif feed == "camera":
			showtoast("Live Camera Feed Started","Live Camera Feed started for a client")
			ws_connections["camera"].add(self)
		else:
			success = False

	def on_close(self):
		try:
			ws_connections["screenshot"].remove(self)
		except KeyError:
			pass
		try:
			ws_connections["camera"].remove(self)
		except KeyError:
			pass

		toast("Live Feed Closed","Live Feed closed for a client")

def WebSocket_SendBytes(feedtype,bytes):
	try:
		[client.write_message(json.dumps({"content":base64.b64encode(bytes),"scale":25,"content-type":"img:base64"})) for client in ws_connections[feedtype]]
	except Exception as e:
		traceback.print_exc()

QUALITY = 30

def startWebSocket_ScreenshotWriter():
	global THREADSSTOP
	while True:
		if len(ws_connections["screenshot"]) >= 1: # Clients connected
			img = pyautogui.screenshot()
			def Processing_Local():
				buffer = io.BytesIO()
				img.resize(img.size,PIL.Image.ANTIALIAS)
				img.save(buffer,format="JPEG",optimize=True,quality=QUALITY)
				bytes = buffer.getvalue()
				threading.Thread(target=WebSocket_SendBytes,args=("screenshot",bytes)).start()
			threading.Thread(target=Processing_Local).start()
		else:
			time.sleep(1)
		if THREADSSTOP:return
def startWebSocket_CameraWriter():
	global THREADSSTOP
	vc = None
	while True:
		if len(ws_connections["camera"]) >= 1: # Clients connected
			if not vc:
				vc = cv2.VideoCapture(1)
			success, frame = vc.read()
			if not success:
				time.sleep(1)
				continue
			def Processing_Local():
				img = PIL.Image.fromarray(frame)
				buffer = io.BytesIO()
				#img.resize(img.size,PIL.Image.ANTIALIAS)
				#img.save(buffer,format="JPEG",optimize=True,quality=QUALITY)
				img.save(buffer,format="JPEG")
				bytes = buffer.getvalue()
				threading.Thread(target=WebSocket_SendBytes,args=("camera",bytes)).start()
			threading.Thread(target=Processing_Local).start()

		else:
			if vc:
				vc = None
			time.sleep(1)
		if THREADSSTOP:return
class LiveHandler(BaseHandler):
	def get(self):
		if not self.checkAuthenticated():return
		self.render(Templates.live)

class LogoutHandler(BaseHandler):
	def get(self):
		if self.checkAuthenticated(redirect=False):generate_new_resource_token()
		self.clear_cookie("Load_Resource_Token")
		self.clear_cookie("FTP_Resource_Token")
		self.redirect("/")
		self.logAction("Log out")
class ScriptsHandler(BaseHandler):
	def get(self,script=""):
		css = script=="css"
		self.set_header("content-type",(css and "text/css" or "application/javascript"))
		path = "./src/"+script+"."+(css and "css" or "js")
		if not ".." in path and os.path.exists(path):
			self.write(open(path,'r').read())
			return
		self.write("""console.error('Tried to fetch unknown script %s')"""%(self.request.uri))


# -------------- FTP -------------------
class FTPRenderHandler(BaseHandler):
	def get(self):
		if not self.FTP_checkAuthenticated():
			return
		self.render(Templates.ftp)
FTPClients = {}
unpack = lambda a:a
def getFTPHiddenFolders():
	return {[o.strip() for o in i.split(":")][0]:[o.strip() for o in i.split(":")][1] for i in open("./FTP_HIDDEN_FOLDERS.settings",'r').readlines() if i.strip()}
class FTPWebSocketHandler(tornado.websocket.WebSocketHandler,BaseHandler):

	def open(self):
		if not FTPClients.get(self):
			FTPClients[self] = {"cwd":"/","illegalCD":False}
	def on_message(self,message):
		try:
			message = json.loads(message)
		except:
			self.write_message(json.dumps({"error":"400 Bad Request"}))
			return
		action = message["action"]or None
		data = message.get("data") or {}


		if not self.FTP_checkAuthenticated(redirect=False):
			password = data["FTPLoginPassword"]or None
			currentpassword = open("./FTP_Password.txt","r").read()
			if currentpassword != password:
				self.write_message(json.dumps({"error":"Incorrect password"}))
				return



		if action == "cd":
			currentdir = FTPClients[self]["cwd"]
			directory = data["dir"]
			password = data.get("password")
			directory = directory.replace("\\","/")
			if FTPClients[self]["illegalCD"] or (directory !="." and not "/" in directory):
				if directory == ".." and not FTPClients[self]["illegalCD"]:
					newdir = "/".join(currentdir.split("/")[:-1])
					newdir = newdir or "/"
				elif FTPClients[self]["illegalCD"]:
					newdir = currentdir+"/"+directory
				else:
					newdir = ("" if currentdir=="/" else currentdir)+"/"+directory

				if FTPClients[self]["illegalCD"] or (os.path.isdir("./ftp/"+newdir) and not os.path.abspath("./ftp/"+newdir) == os.path.abspath(".")):
					password_correct = getFTPHiddenFolders().get(newdir)
					if password_correct and directory != "..":
						shouldsendpasswordIncorrect = False
						passwordIncorrect = password != password_correct
						if password and passwordIncorrect:
							shouldsendpasswordIncorrect = True
						self.write_message(json.dumps({"action":action,"passwordRequired":True,"passwordIncorrect":shouldsendpasswordIncorrect,"cd":directory}))
						if passwordIncorrect: return
					FTPClients[self]["cwd"] = newdir.replace("\\","/")

			self.write_message(json.dumps({"action":action,"error":False,"success":True}))
		elif action == "getCDContents":
			cwd = FTPClients[self]["cwd"]
			afterselect = data.get("afterselect")
			dirlisting = "./ftp"+cwd
			self.write_message(json.dumps({
				"action":action,
				"cwd":cwd,
				"files":[
					{
						"name":file,
						"isfile":os.path.isfile(os.path.join(dirlisting,file)),
						"protected":bool(getFTPHiddenFolders().get(cwd+file.replace("\\","/"))),
						"size":toString_filesize(get_size("./ftp"+cwd+"/"+file.replace("\\","/"))),
						"filesinside":(not bool(getFTPHiddenFolders().get(cwd+file.replace("\\","/"))) and os.path.isdir(os.path.join(dirlisting,file)) and os.listdir(os.path.join(dirlisting,file)) )
					}
					for file in os.listdir(dirlisting) if not "'" in file
					],
				"afterselect":afterselect
				}))
		elif action == "downloadFile":
			file = data["file"]
			cwd = FTPClients[self]["cwd"]
			self.write_message(json.dumps({"action":action,"redirect":"/ftp_download?filename="+os.path.join(cwd,file).replace("\\","/")}))

		elif action == "enableIllegalCD":
			password = data["password"]
			if password == "legal the illegal":
				FTPClients[self]["illegalCD"] = True
				self.write_message("successful.")

		# Write
		elif action == "delFile":
			file = data["file"]
			cwd = FTPClients[self]["cwd"]
			fpath = os.path.join("./ftp"+cwd,file)
			fpath = fpath.replace("\\","/")
			if not "/" in file:

				if os.path.isfile(fpath):
					os.remove(fpath)
				if os.path.isdir(fpath):
					if not getFTPHiddenFolders().get(cwd+file):
						shutil.rmtree(fpath)
			self.write_message(json.dumps({"action":action,"success":True}))
		elif action == "renFile":
			file = data["from"].replace("\\","/")
			file2 = data["to"].replace("\\","/")
			cwd = FTPClients[self]["cwd"]
			fpath = os.path.join("./ftp"+cwd,file)
			fpath2 = os.path.join("./ftp"+cwd,file2)
			if not "/" in file and not "/" in file2:
				print(fpath)
				if not getFTPHiddenFolders().get(cwd+file):
					os.rename(fpath,fpath2)
			self.write_message(json.dumps({"action":action,"success":True}))
		elif action == "newFolder":
			cwd = FTPClients[self]["cwd"]
			newfolder = "New Folder"
			p = os.path.join("./ftp"+cwd,newfolder)
			if not os.path.isdir(p):
				os.mkdir(p)
			self.write_message(json.dumps({"action":action,"afterselect":newfolder}))


	def on_close(self):
		del FTPClients[self]
class FTPUploadHandler(BaseHandler):
	def post(self):
		file = self.request.files["file"][0]
		try:
			data = json.loads(self.get_argument("data"))
		except:
			self.set_status(400)
			self.write("400: Bad Request")
			return
		path = data.get("path")
		if not path or ".." in path:
			return
		print("Upload: "+file["filename"])
		open(os.path.join("./ftp"+path,file["filename"]),'wb').write(file["body"])
		self.write(json.dumps({"success":True}))

class FTPDownloadHandler(BaseHandler):
	def get(self):
		if not self.FTP_checkAuthenticated():
			return
		file_name = self.get_argument("filename","")
		path = ("./ftp"+file_name)
		if not path:
			self.write("Please provide a filename")
			return
		if ".." in path:
			self.write("Illegal .. in filename")
			return
		path = os.path.abspath(path)
		afterfunc = lambda:None
		if getFTPHiddenFolders().get(file_name):
			self.set_header('Content-Type', 'text/html')
			self.write("Cannot download protected folders")
			self.finish()
			return
		self.set_header('Content-Type', 'application/octet-stream')
		firstname = os.path.split(file_name)[-1]
		self.set_header('Content-Disposition', 'attachment; filename=' + ("." in firstname and firstname or firstname+".zip"))
		if not os.path.isfile(path): #zipdir: replace `path` with zip path
			shutil.make_archive("./tempzip", 'zip', path)
			path = "./tempzip.zip"
			afterfunc = lambda: os.remove(path)
		with open(path, 'rb') as f:
			data = f.read()
			self.set_header("Content-Length",len(data))
			self.write(data)
		self.finish()
		afterfunc()
class FTPLoginHandler(BaseHandler):
	def get(self):
		self.render(Templates.ftplogin)
	def post(self):
		currentpassword = open("./FTP_Password.txt","r").read()
		password = self.get_argument("password","")
		if currentpassword != password:
			self.write({"error":"Incorrect password"})
			return
		self.logAction("FTP Log in")
		self.set_secure_cookie("FTP_Resource_Token",open("./FTP_RESOURCE_TOKEN.txt").read())
		self.write({"content":"/ftp"})
class ResourcesHandler(BaseHandler):
	def get(self):
		file_name = self.get_argument("filename","")
		path = ("./resources/"+file_name)
		if not path:
			self.write("Please provide a filename")
			return
		if ".." in path:
			self.write("Illegal .. in filename")
			return
		if not os.path.isfile(path):
			self.write("Unknown file "+file_name)
			return
		buf_size = 4096
		self.set_header('Content-Type', 'application/octet-stream')
		self.set_header('Content-Disposition', 'attachment; filename=' + os.path.split(file_name)[-1])
		with open(path, 'rb') as f:
			while True:
				data = f.read(buf_size)
				if not data:
					break
				self.write(data)
		self.finish()
class SpeedTestHandler(BaseHandler):
	def get(self):
		self.render(Templates.speedtest)
class FaviconHandler(BaseHandler):
	def get(self):
		return self.redirect("/resource?filename=favicon.ico")

ConnectedClients = set()
class InfoWebSocketHandler(tornado.websocket.WebSocketHandler):
	def open(self):
		ConnectedClients.add(self)
	def on_message(self):
		self.write_message(json.dumps({"action":"unknown"}))
	def on_close(self):
		ConnectedClients.remove(self)

class App(tornado.web.Application):
	is_closing = False
	threads = []
	def signal_handler(self, signum, frame):
		print("Wait...")
		self.is_closing = True

	def try_exit(self):
		global THREADSSTOP
		if self.is_closing:
			print("Preparing to exit...")
			print("Disconnecting all clients...")
			[[client.write_message(json.dumps({"action":"servershutdown"})),client.close()] for client in ConnectedClients]
			print("Shutting down webserver...")
			tornado.ioloop.IOLoop.instance().stop()
			print("Cleaning up threads...")
			THREADSSTOP = True
			for i in threads:
				i.join()

			print("Finishing up...")
			sys.exit(0)
	def register_threads(self,threads):
		self.threads += threads
def make_app():
	settings = {
		'debug':True,
		# AutoReload (Uses 2.0%-3.0% of cpu)
		"cookie_secret":"COOKIE_SECRET_91u49cnyt0qgc87tgq07tf97tcwng79w8t97c8rt7ctqctqwocq78wcqo87_SECRET_COOKIE",
	}
	return App([
		(r"/", MainHandler),
		(r"/control",ControlHandler),
		(r"/logout",LogoutHandler),
		(r"/live",LiveHandler),
		(r"/ftp_login",FTPLoginHandler),
		(r"/ftp",FTPRenderHandler),

		(r"/src/(?P<script>\w+)",ScriptsHandler),
		(r"/resource",ResourcesHandler),
		(r"/ftp_download",FTPDownloadHandler),
		(r"/speedtest",SpeedTestHandler),
		(r"/favicon.ico",FaviconHandler),

		(r"/live_websocket",LiveWebSocketHandler),
		(r"/logs_websocket",LogsWebSocketHandler),
		(r"/ftp_websocket",FTPWebSocketHandler),
		(r"/ftp_upload",FTPUploadHandler),
		(r"/info_websocket",InfoWebSocketHandler),
	],**settings),settings

if __name__ == "__main__":
	PORT = 8888
	# Check for updates
	if not BackgroundProcess():
		data = requests.get(UPDATEURL+"?cachebreaker="+str(time.time())).content
		if data != open(__file__,'rb').read():
			if raw_input("Update avalible. Update? (Y/N) :")=="Y":
				open(__file__,'wb').write(data)
				print("Restarting...")
				os.execl(sys.executable, __file__, *sys.argv) 
				quit()


		open("./ftp/AutoRepo/"+__file__,'wb').write(open(__file__,'rb').read())
	app,settings = make_app()
	if not settings.get("debug"): # not debug mode
		generate_new_resource_token()

	signal.signal(signal.SIGINT, app.signal_handler)
	try:
		app.listen(PORT)
	except Exception as e:
		print("FATAL ERROR: "+str(e))
		print("Killing Process with port "+str(PORT)+"...")
		from psutil import process_iter

		for proc in process_iter():
			for conns in proc.connections(kind='inet'):
				if conns.laddr.port == PORT:
					proc.send_signal(signal.SIGTERM) # or SIGKILL
		print("Killed")
		print("Retrying port in a second...")
		time.sleep(1)
		try:
			app.listen(PORT)
		except Exception as e:
			print("error while retrying port: "+str(e))
			sys.exit(0)
		del process_iter
	ip = socket.gethostbyname(socket.gethostname())
	print("Started server")
	print("Get Control by visiting http://%s:%d/"%(ip,PORT))
	threads = [
		threading.Thread(target=startWebSocket_ScreenshotWriter),
		threading.Thread(target=startWebSocket_CameraWriter)
	]
	[thread.start() for thread in threads]
	app.register_threads(threads)

	tornado.ioloop.PeriodicCallback(app.try_exit, 1000).start()
	tornado.ioloop.IOLoop.instance().start()
