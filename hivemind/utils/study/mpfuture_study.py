# https://docs.python.org/3/library/concurrent.futures.html#module-concurrent.futures
# https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ThreadPoolExecutor
import concurrent.futures
import urllib.request

URLS = ['http://www.foxnews.com/',
        'http://www.cnn.com/',
        'http://europe.wsj.com/',
        'http://www.bbc.co.uk/',
        'http://some-made-up-domain.com/']

# Retrieve a single page and report the URL and contents
def load_url(url, timeout):
    with urllib.request.urlopen(url, timeout=timeout) as conn:
        return conn.read()

items = [1, 2, 3]
dict_for = {item: item*2 for item in items}

# We can use a with statement to ensure threads are cleaned up promptly
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    # Start the load operations and mark each future with its URL
    future_to_url = {
        executor.submit(load_url, url, 60): url for url in URLS
    }
    print('future_to_url: \n', future_to_url)
    #  {<Future at 0x7f8943f2a910 state=running>: 'http://www.foxnews.com/', <Future at 0x7f89459a3a30 state=running>: 'http://www.cnn.com/', <Future at 0x7f89459a3e20 state=running>: 'http://europe.wsj.com/', <Future at 0x7f89459ac280 state=running>: 'http://www.bbc.co.uk/', <Future at 0x7f89459ac6a0 state=running>: 'http://some-made-up-domain.com/'}
    
    for future in concurrent.futures.as_completed(future_to_url):
        # as_completed: Returns an iterator over the Future instances 
        # (possibly created by different Executor instances) 
        # given by fs that yields futures as they complete 
        # (finished or cancelled futures). Any futures given by 
        # fs that are duplicated will be returned once. Any futures 
        # that completed before as_completed() is called will be yielded first. 
        # The returned iterator raises a concurrent.futures.TimeoutError 
        # if __next__() is called and the result isn’t available after 
        # timeout seconds from the original call to as_completed(). 
        # timeout can be an int or float. If timeout is not specified or None, 
        # there is no limit to the wait time.

        url = future_to_url[future]
        try:
            data = future.result()
        except Exception as exc:
            print('%r generated an exception: %s' % (url, exc))
        else:
            print('%r page is %d bytes' % (url, len(data)))



# with ThreadPoolExecutor(max_workers=1) as executor:
#     future = executor.submit(pow, 323, 1235)
#     print(future.result())


# def main():
