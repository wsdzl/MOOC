#HTTP大文件多线程下载，支持断点续传

from ThreadPool import *
from time import sleep
import os
import requests

def _len(url):
	headers = {
		'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML\
		, like Gecko) Chrome/50.0.2661.102 Safari/537.36',
		'Range': 'bytes=0-0',
		'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
	}
	with requests.get(url, headers=headers) as r:
		length = r.headers['Content-Range']
		if length.find('0-0/') == -1:
			length = None
		else:
			length = length.split('0-0/')[-1]
			length = int(length) if length else 0
	if not length:
		del headers['Range']
		with requests.head(url, headers=headers) as r:
			length = r.headers['Content-Length']
			length = int(length) if length else 0
	return length

def _download_bf(url, bfs, i, tmp):
	bf = bfs[i][1]
	headers = {'Range': bf}
	tmp_path = os.path.join(tmp, '%s.tmp' % i)
	if os.path.isfile(tmp_path):
		fsize = os.path.getsize(tmp_path)
		range_size = bf.split('bytes=')[-1].split('-')
		range_size = int(range_size[1]) - int(range_size[0]) + 1
		if fsize == range_size:
			result = (True, tmp_path)
			bfs[i] = result
			return
		else:
			os.unlink(tmp_path)
	try:
		res = requests.get(url, headers=headers, timeout=2)
		res.raise_for_status()
		with open(tmp_path, 'wb') as f:
			f.write(res.content)
	except:
		if os.path.isfile(tmp_path): os.unlink(tmp_path)
		_download_bf(url, bfs, i, tmp)
		return
	result = (True, tmp_path)
	bfs[i] = result

def _merge(bfs, fn, tmp):
	with open(fn, 'wb') as f:
		for bf_path in map(lambda x:x[1], bfs):
			with open(bf_path, 'rb') as bf:
				f.write(bf.read())
			os.unlink(bf_path)
	os.rmdir(tmp)

def _count(bfs, bfsz, length, end):
	count = list(map(lambda x:int(x[0]), bfs))
	end_done = count[-1]
	count = sum(count)
	if count == len(bfs):
		return 'done'
	count *= bfsz
	if end_done:
		count = count - bfsz + end
	percent = count * 1000 // length / 10
	count = count / 1024 / 1024 * 10 // 1 / 10
	length = length / 1024 / 1024 * 10 // 1 / 10
	return (str(percent) + '%', '%sMB' % count, '%sMB' % length)

def download(url, fn, threads=30, bfsz=1048576, sep=0.2):
	name = fn.split(os.path.sep)[-1]
	tmp = os.path.join('.', 'tmp_%s' % name)
	if not os.path.isdir(tmp): os.makedirs(tmp)
	length = _len(url)
	_length = length / 1
	end = None
	at = 0
	bfs = []
	while length > 0:
		if length > bfsz:
			bf = 'bytes=%s-%s' % (at, at + bfsz - 1)
		else:
			bf = 'bytes=%s-%s' % (at, at + length - 1)
			end = length
		bfs.append((False, bf))
		at += bfsz
		length -= bfsz
	with Pool(threads) as pool:
		for i in range(len(bfs)):
			pool.add(_download_bf, (url, bfs, i, tmp))
	while True:
		status = _count(bfs, bfsz, _length, end)
		if status == 'done':
			yield 'Merging...'
			break
		yield status
		sleep(sep)
	_merge(bfs, fn, tmp)
	yield 'done'

if __name__ == '__main__':
	import sys
	if len(sys.argv) == 1:
		os._exit(0)
	dirname = '.'
	if len(sys.argv) == 3:
		dirname = os.path.join('.', sys.argv[2])
		if not os.path.isdir(dirname): os.makedirs(dirname)
	with open(sys.argv[1]) as f:
		urls = [i.strip() for i in f]
		num = len(urls)
		for i in range(num):
			url = urls[i]
			filename = url.split('/')[-1]
			filepath = os.path.join(dirname, filename)
			if os.path.isfile(filepath):
				print('%s/%s %s -> %s' % (i+1, num, url, filepath))
				continue
			downloading = download(url, filepath)
			last_info = ''
			for status in downloading:
				if type(status) == tuple:
					info = ('%s %s/%s: ' % status) + url
				elif status == 'Merging...':
					info = '%s -> Merging to... -> %s' % (url, filename)
				if info != last_info:
					print(' ' * len(last_info),end='\r')
					print(info,end='\r')
					last_info = info
			print(' '*len(info),end='\r')
			print('%s/%s %s -> %s' % (i+1, num, url, filepath))