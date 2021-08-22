def random_sample():
    from random import randint, sample
    ret = [[0]*7]*7
    dummy = []

    for i in range(49):
        dummy += [randint(0, 4)]

    for i in range(7):
        ret[i] = dummy[7*i:7*(i+1)]

    return ret

    
from pprint import pprint
pprint(random_sample())


