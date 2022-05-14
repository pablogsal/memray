import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("results_benchmark_no_pymalloc.txt", names=['test', 'base', 'memray', 'fil'])
df = df.set_index("test")
orig = df
df['fil'] = df["fil"] / df["base"]
df['memray'] = df["memray"] / df["base"]

df =df[df['memray'] > 1]
df = df[df['fil'] > 1]

x = df['memray']/df['fil']
(x[x<3]).hist()
print(x)

plt.savefig("graph.png", dpi=300)
plt.clf()

# df = df[["memray", "fil"]]
x.plot.barh(figsize=(20,70))
plt.savefig("graph1.png", dpi=300)


