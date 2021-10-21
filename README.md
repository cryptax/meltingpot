**Meltingpot** is a simple FTP server honeypot, written in Python.

Features:

- Supports **passive mode**. Server will choose ports between 30000-30009 (this is configurable). *Active mode* is not supported as it would require the FTP server to connect to an external unknown port, and this will be blocked by firewalls.
- **Logs** all commands in JSON file. Those logs can be processed by Filebeat, logstash etc.
- Attackers who connect will see a directory. They will be able to get/put files in the directory, but won't be able to get out of the directory (for security reasons), delete or rename files.

# Deploy

1. Configure `meltingpot.cfg` and `creds.cfg` to  your needs
2. Inside `./fs` put the files you want to share

```
docker-compose build
docker-compose up -d
```

# Example

```
$ ftp 127.0.0.1 2221
Connected to 127.0.0.1.
220 FTP Ready
Name (127.0.0.1:cryptax): anonymous
331 Looking up password
Password:
230 Login successful
Remote system type is Unix.
ftp> passive
Passive mode on.
ftp> ls
227 Entering Passive Mode (0,0,0,0,117,48).
150 Opening ASCII mode data connection.
-rw-rw-r-- 1 root root 0 Sep 21 07:49 testfile
226 Directory send OK
ftp> quit
221 Goodbye.
```

# Passive mode on an instance running Docker

Do not forget to customize `public_ip`:

```
# This is the public IP address of the host
# This IP address will be returned to the client when it asks for passive connection
public_ip = 0.0.0.0
```

For example, if you are running Meltingpot in a Docker container in a Google instance, p`public_ip` should be the public IP address of  your Google instance. Otherwise, passive communication won't work (even with the right ports opened) because the FTP server needs an IP address accessible from Internet for the client to connect to the passive ports.

# References

- [List of FTP commands](https://en.wikipedia.org/wiki/List_of_FTP_commands)






