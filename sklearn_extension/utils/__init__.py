from sklearn.preprocessing import LabelBinarizer
from sklearn.utils import column_or_1d, is_scalar_nan
import pandas as pd
import numpy as np
import warnings
import statsmodels.api as sm


def force_zero_one(y):
    """" Convert two-class labels to 0 and 1
    ex. [-1, 1, -1, -1, 1] => [0, 1, 0, 0, 1]
    """
    y = column_or_1d(y, warn=True)
    if len(set(y)) != 2:
        raise ValueError('The label should have exactly two categories')
    return LabelBinarizer().fit_transform(y).ravel()


def make_series(i, reset_index=True) -> pd.Series:
    """ Convert an iterable into a Pandas Series"""
    if isinstance(i, pd.DataFrame):
        series = i.iloc[:, 0]
    else:
        series = pd.Series(i)
    # make index starts from 0
    if reset_index:
        series = series.reset_index(drop=True)
    return series


def map_series(X: pd.Series, mapping: dict, unseen=0, fill=-99):
    def _map(x):
        if is_scalar_nan(x):
            return fill
        else:
            return mapping.get(x, unseen)
    return X.map(_map)


def _searchsorted(a, v):
    """ Same as np.searchsorted(a, v, side='left') but faster for our purpose."""
    for i, c in enumerate(a):
        if c > v:
            return i
    else:
        return len(a)


def searchsorted(a, v, fill=-1):
    """ Encode values in v with ascending cutoff points in a. Similar to numpy.searchsorted
        Left open right close except for the leftmost interval, which is close at both ends.
    """
    encoded = list()
    for value in v:
        if is_scalar_nan(value):
            encoded.append(fill)
        elif value == min(a):
            # the leftmost interval close at both ends
            encoded.append(1)
        else:
            encoded.append(_searchsorted(a, value))
    return encoded


def assign_group(x, bins):
    """ Assign the right cutoff value for each value in x except for the first interval
        which take the left cutoff value
        ex. assign_group(range(6), [0, 2, 4]) => [0, 2, 2, 4, 4, np.inf]
    """
    # add infinite at the end
    bins = np.array(bins)
    groups = list()
    for v in x:
        if is_scalar_nan(v):
            groups.append(v)

        elif v <= bins[0]:
            groups.append(bins[0])
            continue
        
        else:    
            # find the cutoff value that's larger or equal than the current value
            idx = np.argmax(bins >= v)
            if idx > 0:
                groups.append(bins[idx])
            else:
                # none of the cutoff points is larger than the value
                groups.append(np.inf)            
    return groups


def wrap_with_inf(bins):
    """ Given a series of cutoff points, add positive and negative infinity
        at both ends of the cutoff points
     """
    return np.unique(list(bins) + [np.inf, -np.inf])


def encode_with_nearest_key(series: pd.Series, key):
    """ Find the value with the nearest key to the given new key value
        Only works when the series has a numerical index
    """
    try:
        return series[key]
    except KeyError:
        nearest_key_idx = np.abs((series.index - key)).argmin()
        return series[series.index[nearest_key_idx]]


def encode_with_default_value(series: pd.Series, key, default=0):
    """ Find the value in Pandas Series with default value"""
    try:
        return series[key]
    except KeyError:
        return default


def sort_columns_logistic(X: pd.DataFrame, y, cols=None):
    """ Sort columns according to wald_chi2 """
    cols = cols or X.columns.tolist()
    X = sm.add_constant(X.copy())
    
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        logit_result = sm.Logit(y, X[cols + ['const']]).fit(method='bfgs', disp=False)
    
    wald_chi2 = np.square(logit_result.params / np.square(logit_result.bse))
    wald_chi2 = pd.DataFrame({'chi2': wald_chi2, 'feature': cols + ['const']})
    sorted_cols = wald_chi2.sort_values('chi2', ascending=False).feature.tolist()
    sorted_cols.remove('const')
    return sorted_cols


def sort_columns_tree(X: pd.DataFrame, y, cols=None):
    """ Sort columns according to feature importance in tree method"""
    from sklearn.ensemble import RandomForestClassifier

    cols = cols or X.columns.tolist()
    RF = RandomForestClassifier(n_estimators=100)
    RF.fit(X[cols], y)
    importance = pd.DataFrame({'importance': RF.feature_importances_, 'feature': cols})
    sorted_cols = importance.sort_values('importance', ascending=False).feature.tolist()
    return sorted_cols
