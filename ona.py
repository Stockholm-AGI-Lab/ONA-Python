# Hyperparams
TRUTH_PROJECTION_DECAY = 0.8
TRUTH_EVIDENTIAL_HORIZON = 1.0

def truth_deduction(v1, v2):
    (_, c1), (f2, c2) = v1, v2
    f = f2*f2
    return (f, c1 * c2 * f)

def truth_w2c(w):
    return w / (w + TRUTH_EVIDENTIAL_HORIZON)

def truth_induction(v2, v1):
    ((f1, c1), (f2, c2)) = (v1, v2)
    return (f2, truth_w2c(f1 * c1 * c2))

def truth_intersection(v1, v2):
    ((f1, c1), (f2, c2)) = (v1, v2)
    return (f1*f2, c1*c2)

