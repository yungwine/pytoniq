import re


# class
# my = re.compile(r"\s([^:]+):(\(.+\))")
# my = re.compile(r"\s([^:]+):(\S+)")
my = re.compile(r"\s([^:]+):(\(.+\)|\S+)")

# liteServer.libraryResult result:(vector liteServer.libraryEntry) = liteServer.LibraryResult;


# my = re.compile(r"\(.+\)")

s = 'liteServer.getLibraries library_list:(vector int256) = liteServer.LibraryResult;'
print(my.findall(s))
# print(my.findall('liteServer.libraryResult result:(vector liteServer.libraryEntry) = liteServer.LibraryResult;'))

# print(my.findall('aef  (abc)'))