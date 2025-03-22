#!/usr/bin/env python3
#
# round certain keys within a dictionary
# and don't round others like datetimes or strings
#
# Marc Compere, comperem@erau.edu
# created : 25 Sep 2023
# modified: 25 Sep 2023

# round only the keys that make sense to round
def roundOnlyRoundableDictKeys(myData, keysToRound):
    myDataRounded = {}
    for key in myData:
        if key in keysToRound:
            myDataRounded[key] = round(myData[key], 8)
        else:
            myDataRounded[key] = myData[key]
    return myDataRounded


# example usage
if __name__ == "__main__":
    from datetime import datetime

    from roundOnlyRoundableDictKeys import roundOnlyRoundableDictKeys

    # tNow and the string keys cannot be rounded
    myData = {
        "tNow": datetime.now(),
        "var1": 0.1 + 0.2,
        "var2": 20.00000000004,
        "c": 3,
        "myCoolString": "hola, amigo",
    }

    print("\n------------------- BEFORE ROUNDING -------------------")
    for k, v in myData.items():
        print("\t{0} = {1}".format(k, v))

    keysToRound = ["var1", "var2"]
    # keysToRound=[] sending in nothing does a shallow copy, element by element
    print("keysToRound={0}".format(keysToRound))
    myDataRounded = roundOnlyRoundableDictKeys(myData, keysToRound)

    print("\n------------------- AFTER ROUNDING -------------------")
    for k, v in myDataRounded.items():
        print("\t{0} = {1}".format(k, v))
