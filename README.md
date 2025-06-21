# AWS S3/SQS tunnel

## 2025 Update:
1. This was a research project from 2023 regarding the Great-Firewall-of Iran (GFI). Its aim was to tunnel out of Iran when there is a total Internet Lockdown. It works when other tricks like v2ray, domain-fronting or DNS tunnel fail.
2. Feel free to add this trick to v2ray or gost.
3. There were many other tricks but this is the 'easiest' that worked when Iran went from normal DPI to total lockdown. In total lockdown only AWS and discord (and a very few other IP addresses and domain names) were reachable. Discord can also be used for tunneling but is slower.

---

This PoC solves [#20](https://github.com/hackerschoice/gfi/issues/20).

This trick tunnels via AWS's Simple-Queue-Service (SQS). It has some advantages over S3-bucket-tunneling:
1. SQS are faster than S3 buckets (less latency).
2. S3 can be blocked by SNI-filtering. SQS can not be blocked that way because SQS uses the main AWS endpoint (`sqs.<REGION>.amazonaws.com`). The autocrats have never dared to block the main endpoint (and doing so would put their own criticial infra at risk)

Requirements:
---
  - Install boto3 AWS python SDK
  - Configure boto3 authentication in the envrionment
1. Create queues: python sqscreate.py
2. Fix queues in scripts:
  - awsproxy.py:  tx_url, rx_url
  - sqsrouter.py: tx_url, rx_url
3. Run Router listens on SQS and forwards traffic to remote:
  - NOTE: could have this running on outside world
  - python sqsrouter.py
4. Run local proxy server:
  - NOTE: this is the SOCKS5 server running on users local machine
  - config HOST, PORT in awsproxy.py
  - python awsproxy.py
5. Connect a user client:
  - curl -v  --socks5 172.29.0.1:9011 https://www.thc.org
  - ssh -o 'ProxyCommand /usr/bin/nc -x 127.0.0.1:9011 %h %p' root@host.com

IMPORTANT:
---
- this is PoC, only establishes connection once, doesn't clear state
- So restart to test every new connection
