#!/usr/bin/python3
# Inspired from https://gist.github.com/scturtle/1035886#file-ftpserver-py

import socket
import configparser
import re
import json
import traceback
import os
import time
import hashlib
from threading import Thread

CONFIG_FILE='./meltingpot.cfg'
DEBUG = True


class FtpServerThread(Thread):

    def __init__(self, conn, addr, meltingpot):
        self.conn = conn
        self.addr = addr
        self.meltingpot = meltingpot
        self.is_logged = False
        self.pasv_mode = False
        self.binary = False
        self.user = ''
        self.datasock = None
        Thread.__init__(self)

    def log(self, message):
        log = {}
        log['src_ip'] = self.addr[0]
        log['src_port'] = self.addr[1]
        log['message'] = message
        f = open(self.meltingpot.logfile, "a+")
        f.write(json.dumps(log))
        f.write('\n')
        f.close()
        if DEBUG:
            print("[debug] {0}: {1}:{2} {3}".format(self.meltingpot.logfile, self.addr[0], self.addr[1], message))

    def run(self):
        if DEBUG:
            print("[debug] FtpServerThread.run() for {0}:{1}".format(self.addr[0], self.addr[1]))

        while True:
            data = self.conn.recv(1024).decode()
            if not data:
                break
            self.log(data)

            try:
                func=getattr(self,data[:4].strip().upper())
                active = func(data)
                if not active:
                    break
            except Exception as e:
                print("Unknown command {0}: gracefully closing connection".format(e))
                if DEBUG:
                    traceback.print_exc()
                self.conn.send(b'500 Sorry.\r\n')
                break

        if DEBUG:
            print("[debug] closing connection and thread")
        self.conn.close()



    def USER(self, data):
        # sanitize username and keep only alphanumeric
        pattern = re.compile('[\W_]+', re.UNICODE)
        self.user = pattern.sub('', data[5:])
        self.conn.sendall(b'331 Looking up password\n')
        return True

    def PASS(self, data):
        # sanitize password and keep only some characters
        pattern = re.compile('[\W_#!@]+', re.UNICODE)
        password = pattern.sub('', data[5:])
        message = "login attempt {0}/{1}".format(self.user,password)
        self.is_logged = False
        try:
            if self.meltingpot.users[self.user] == password or self.user == 'anonymous':
                message += ' success'
                self.conn.sendall(b'230 Login successful\n')
                self.is_logged = True
        except KeyError as e:
            if DEBUG:
                print("[debug] unknown user: {0}".format(self.user))

        if not self.is_logged:
            message += ' failed'
            self.conn.sendall(b'221 Goodbye!\n')

        self.log(message)
        return self.is_logged
            
    def SYST(self, data):
        self.conn.sendall(bytes(self.meltingpot.system+'\n', 'utf-8'))
        return True

    def OPTS(self,data):
        self.conn.send(b'200 OK.\r\n')
        return True

    def QUIT(self, data):
        self.conn.send(b'221 Goodbye.\r\n')
        return False

    def NOOP(self, data):
        self.conn.send(b'200 OK.\r\n')
        return True

    def TYPE(self,data):
        try:
            mode=data[5]
            # A and A N = turn binary flag off
            # I and L 8 = turn binary flag on
            if mode =='I' or mode == 'L':
                self.conn.send(b'200 Binary mode.\r\n')
                self.binary=True
            else:
                self.conn.send(b'200 ASCII mode.\r\n')
                self.binary = False
                
            if DEBUG:
                print("[debug] Setting mode={0} binary={1}".format(mode,binary))

            return True
        
        except IndexError as e:
            if DEBUG:
                print("[debug] IndexError: data={0} exc={1}".format(data,e))
        return False
                
            

    def PASV(self,data): # from http://goo.gl/3if2U
        self.pasv_mode = True
        self.servsock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.servsock.bind((self.meltingpot.host,0))
        self.servsock.listen(1)
        ip, port = self.servsock.getsockname()
        print("[+] Passive Mode: opening {0}:{1}".format(ip, port))
        self.conn.send('227 Entering Passive Mode (%s,%u,%u).\r\n' %
                (','.join(ip.split('.')), port>>8&0xFF, port&0xFF))
        return True
        
    def PORT(self, data):
        if self.pasv_mode:
            self.servsock.close()
            self.pasv_mode = False
            
        l=data[5:].split(',')
        self.dataAddr='.'.join(l[:4])
        self.dataPort=(int(l[4])<<8)+int(l[5])
        if DEBUG:
            print("[debug] PORT: addr={0} port={1}".format(self.dataAddr, self.dataPort))
        self.conn.send(b'200 PORT command successful\r\n')
        return True

    def CWD(self, data):
        # we don't support changing directories as we want to make sure not to exit ftproot
        self.conn.sendall(b'550 No such file or directory\n')
        return True

    def PWD(self, data):
        self.conn.sendall(b'257 "/"\n')
        return True

    def CDUP(self, data):
        self.conn.sendall(b'200 Okay\n')
        return True

    def MKD(self, data):
        self.conn.send(b'257 Directory created.\r\n')
        return True

    def RMD(self, data):
        self.conn.send(b'450 Not allowed.\r\n')
        return True

    def DELE(self, data):
        self.conn.send(b'450 Not allowed.\r\n')
        return True

    def RNTO(self, data):
        self.conn.send(b'250 File renamed.\r\n')
        return True

    def RNFR(self, data):
        self.conn.send(b'350 Ready.\r\n')
        return True

    def REST(self, data):
        self.conn.send(b'250 File position reseted.\r\n')
        return True

    def STRU(self, data):
        self.conn.send(b'200 OK\n')
        return True

    def MODE(self, data):
        self.conn.send(b'200 OK\n')
        return True
    
    def start_datasock(self):
        if self.pasv_mode:
            self.datasock, addr = self.servsock.accept()
            if DEBUG:
                print("[debug] passive mode - opening data sock on {0}:{1}".format(addr[0], addr[1]))
        else:
            # if dataAddr and port haven't been set, connection will fail
            self.datasock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            self.datasock.connect((self.dataAddr,self.dataPort))
            if DEBUG:
                print("[debug] opening data sock on {0}:{1}".format(self.dataAddr, self.dataPort))

    def stop_datasock(self):
        if DEBUG:
            print("[debug] closing data sock")
        self.datasock.close()
        if self.pasv_mode:
            self.servsock.close()

    def LIST(self, data):
        self.conn.send(b'150 Opening ASCII mode data connection.\r\n')

        try:
            self.start_datasock()
        except Exception as e:
            if DEBUG:
                print("[debug] opening data sock error: ",e)
            self.conn.sendall(b'425 Connection failed\n')
            return False
                
        try:
            for t in os.listdir(self.meltingpot.ftproot):
                k=self.toListItem(os.path.join(self.meltingpot.ftproot,t))
                self.datasock.send(bytes(k+'\r\n', 'utf-8'))
            message='226 Directory send OK'
            self.stop_datasock()    
        except Exception as e:
            traceback.print_exc()
            if DEBUG:
                print("[debug] LIST error: data={0} e={1}".format(data,e))
            message='451 Directory KO'
        
        self.conn.send(bytes(message+'\r\n', 'utf-8'))
        return True

    def NLST(self,data):
        return self.LIST(data)
        
    def toListItem(self,fn):
        st=os.stat(fn)
        fullmode='rwxrwxrwx'
        mode=''
        for i in range(9):
            mode+=((st.st_mode>>(8-i))&1) and fullmode[i] or '-'
        d=(os.path.isdir(fn)) and 'd' or '-'
        ftime=time.strftime(' %b %d %H:%M ', time.gmtime(st.st_mtime))
        return d+mode+' 1 root root '+str(st.st_size)+ftime+os.path.basename(fn)

    def openFile(self, data, themode='r'):
        try:
            filename=os.path.join(self.meltingpot.ftproot,data[5:-2])
            mode = themode
            if self.binary:
                mode += 'b'
            f=open(filename,mode)
            return f
        except Exception as e:
            if DEBUG:
                print("[debug] Exception in openFile: filename={0} file exception={1}".format(filename,e))
            self.conn.send(b'451 Cannot perform operation\r\n')
            return None
    
    def RETR(self, data):
        fi = self.openFile(data, 'r')
        if fi == None:
            return False

        # we read the file and send it over data socket connection
        self.conn.send(b'150 Opening data connection for RETR.\r\n')
        d= fi.read(1024)
        self.start_datasock()
        while d:
            self.datasock.send(bytes(d, 'utf-8'))
            d=fi.read(1024)
            
        fi.close()
        self.stop_datasock()
        self.conn.send(b'226 Transfer complete.\r\n')
        log("Downloaded file {0}".format(data[5:-2]))
        return True

    def STOR(self,data):
        fo = self.openFile(data,'w')
        if fo == None:
            # An exception occurred with that file
            return False

        try:
            tmpname = os.path.join(self.meltingpot.upload_dir, '.tmp')
            copy = open(tmpname, 'wb')
            self.conn.send(b'150 Opening data connection.\r\n')
            self.start_datasock()
            sha256_hash = hashlib.sha256()
            while True:
                d=self.datasock.recv(1024).decode()
                if not d: break
                sha256_hash.update(bytes(d, 'utf-8'))
                fo.write(d)
                copy.write(bytes(d, 'utf-8'))
            fo.close()
            copy.close()
            self.stop_datasock()

            # move tmp file
            realname = sha256_hash.hexdigest()
            self.log("Uploaded file {0}".format(realname))
            os.rename(tmpname, os.path.join(self.meltingpot.upload_dir, realname))

        except Exception as e:
            print("[ERROR] cannot open copy file: upload_dir={0} e={1}".format(self.meltingpot.upload_dir, e))
            traceback.print_exc()
            return False

        self.conn.send(b'226 Transfer complete.\r\n')
        return True

class meltingpot:
    def __init__(self, configfile=CONFIG_FILE):
        self.configfile = configfile
        self.configparser = configparser.RawConfigParser()
        self.configparser.read(configfile)

        self.host = self.configparser.get('general','host')
        self.port = self.configparser.getint('general', 'port')
        self.banner = self.configparser.get('general', 'banner')
        self.system = self.configparser.get('general', 'system')
        self.logfile = self.configparser.get('general', 'logfile')
        self.creds = self.configparser.get('general', 'credentials_file')
        self.ftproot = self.configparser.get('general', 'ftproot')
        self.upload_dir = self.configparser.get('general', 'upload_dir')

        assert os.path.isdir(self.upload_dir), "[ERROR] Please create {0} directory".format(self.upload_dir)
        assert os.path.isdir(self.ftproot), "[ERROR] ftproot directory does not exist: {0}".format(self.ftproot)
            
        self.load_allowed_credentials(self.creds)
        
        self.init_server()

    def load_allowed_credentials(self, filename):
        f = open(filename,'r')
        lines = f.read().split('\n')
        self.users = {}
        for line in lines:
            u_p  = line.split(':')
            if len(u_p) >= 2:
                username = u_p[0]
                password = u_p[1]
                self.users[username] = password
        
    def init_server(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.bind((self.host, self.port))
        self.s.listen(30) # backlog
        print("[+] Meltingpot is running on port {0}".format(self.port))
        while True:
            conn, addr = self.s.accept()
            print("Incoming connection from IP: {0}:{1}".format(addr[0], addr[1]))
            conn.sendall(bytes(self.banner+'\n', 'utf-8'))
            FtpServerThread(conn, addr, self).start()

if __name__ == '__main__':
    melting = meltingpot()
    
