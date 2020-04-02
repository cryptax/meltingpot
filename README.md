**Meltingpot** is a simple FTP server honeypot, written in Python.

Features:

- Supports **passive mode**. Server will choose ports between 30000-30009 (this is configurable). *Active mode* is not supported as it would require the FTP server to connect to an external unknown port, and this will be blocked by firewalls.
- **Logs** all commands in JSON file. Those logs can be processed by Filebeat, logstash etc.
- Attackers who connect will see a directory. They will be able to get/put files in the directory, but won't be able to get out of the directory (for security reasons), delete or rename files.

Deploy:

```
docker-compose build
docker-compose up -d
```






