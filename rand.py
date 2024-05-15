import pandas as pd 


def test(name):
    ret_arr=[]
    df = pd.read_csv("midcap_signals/"+name+".csv")
    x=False
    for index,row in df.iterrows():
        if row['Signal']=="Buy" and x is False:
            low = row['Low']
            high = row['High']
            x=True
        elif row['Signal']=="Sell" and x is True:
            high = row['High']
            ret_arr.append(((high-low)/low)*100)
            x=False  
    print("the return for:"+name)
    print(sum(ret_arr)/len(ret_arr)) if len(ret_arr) > 0 else print("No returns to calculate")
    print(ret_arr)


test("TRENT-EQ")


