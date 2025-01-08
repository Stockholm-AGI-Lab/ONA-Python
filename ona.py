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

def truth_projection(v, original_time, target_time):
    f, c = v
    difference = abs(target_time - original_time)
    return (f, c * (TRUTH_PROJECTION_DECAY ** difference))

def truth_eternalize(v):
    f, c = v
    return (f, truth_w2c(c))

def temporal_op_induction(event1, operator, event2):
    (term1, occurrence_time1, truth1) = event1
    (term2, occurrence_time2, truth2) = event2
    (term_op, occurrence_time3, truth3) = operator
    # TODO include op in calculation
    truth2_to_op = truth_projection(truth2, occurrence_time2, occurrence_time3)
    truth23 = truth_intersection(truth2_to_op, truth3)
    truth23_to_1 = truth_projection(truth23, occurrence_time3, occurrence_time1)
    truth = truth_eternalize(truth_induction(truth1, truth23_to_1))
    # 2* to distinguish (a =/> b) from (b =/> a)
    return ((term2, term_op, term1), truth)