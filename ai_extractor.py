from newspaper import Article
a = Article("https://www.seriouseats.com/korean-marinated-spinach-banchan-sigeumchi-namul")
a.download(); a.parse()
print(a.title)
print(a.text)
