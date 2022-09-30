table_data = [["a", "b", "c"], ["aaaaaaaaaaaaa", "b", "c"], ["a", "bbbbbbbbbb", "c"]]
for row in table_data:
    print("{: <40} {: <40} {: <40}".format(*row))
