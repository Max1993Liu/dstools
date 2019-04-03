from sklearn.base import BaseEstimator, TransformerMixin
from scipy.stats import skew    
import pandas as pd
import numpy as np
import warnings


from sklearn.utils import check_array, column_or_1d, assert_all_finite
from sklearn.utils.validation import check_is_fitted
from sklearn.exceptions import NotFittedError


def _encode_python(values, uniques=None, encode=False, unseen='warn'):
    """ Modified from the Scikit version except handles unseen values"""
    if uniques is None:
        uniques = sorted(set(values))
        uniques = np.array(uniques, dtype=values.dtype)
    if encode:
        table = {val: i for i, val in enumerate(uniques)}
        try:
            encoded = np.array([table[v] for v in values])
        except KeyError as e:
            msg = "y contains previously unseen labels: %s" % str(e)
            if unseen in ('silent', 'warn'):
                UNSEEN = len(uniques)
                encoded = np.array([table.get(v, UNSEEN) for v in values])
                if unseen == 'warn':
                    warnings.warn(msg)
            elif unseen == 'raise':
                raise ValueError("y contains previously unseen labels: %s"
                                 % str(e))
            else:
                raise ValueError('The supported options for `unseen` are: {}'
                                 .format(['silent', 'warn', 'raise']))
        return uniques, encoded
    else:
        return uniques


class NormDistOutlierRemover(BaseEstimator, TransformerMixin):
    """ Removing outliers assuming data is independent and followes normal distribution
        Each series will be within the range of [mu - n_sigma * std, mu + n_sigma * std]
    """
    def __init__(self, n_sigma=3, cols=None, error='warn'):
        """
        :param cols: A list of column names to apply transformations, default for all the columns
        :param error: Specify the action when the DataFrame passed to transform doesn't have all the columns,
            supported actions are ['raise', 'ignore', 'warn']
        """
        self.n_sigma = n_sigma
        if isinstance(cols, str):
            self.cols = [cols]
        else:
            self.cols = cols
        self.error = error

    def fit(self, X: pd.DataFrame, y=None):
        X = X[self.cols] if self.cols else X
        self.cols = self.cols or X.columns

        self.mean_ = X.mean()
        self.std_ = X.std()
        return self

    def transform(self, X: pd.DataFrame, y=None):
        check_is_fitted(self, ['mean_', 'std_'])
        x = X.copy()

        # copy instance variable to local variable
        _mean, _std, n_sigma = self.mean_, self.std_, self.n_sigma
        for col in self.cols:
            if col not in x:
                msg = 'Column {} is not found in the DataFrame'.format(col)
                if self.error == 'raise':
                    raise ValueError(msg)
                if self.error == 'warn':
                    warnings.warn(msg)

            lower_bound = _mean[col] - n_sigma * _std[col]
            upper_bound = _mean[col] + n_sigma * _std[col]
            x.loc[x[col] > upper_bound, col] = upper_bound
            x.loc[x[col] < lower_bound, col] = lower_bound
        return x


class IQROutlierRemover(BaseEstimator, TransformerMixin):
    """ Removing outlier based on IQR,
        Each series will be in the range of [Q1 - multiplier * IQR , Q3 + multiplier]
    """
    def __init__(self, multiplier=1.5, cols=None, interpolation='nearest', error='warn'):
        """
        :param interpolation: interpolation used in calculating the quantile
        :param cols: A list of column names to apply transformations, default for all the columns
        :param error: Specify the action when the DataFrame passed to transform doesn't have all the columns,
            supported actions are ['raise', 'ignore', 'warn']
        """
        self.multiplier =multiplier
        self.interpolation = interpolation
        if isinstance(cols, str):
            self.cols = [cols]
        else:
            self.cols = cols
        self.error = error

    def fit(self, X: pd.DataFrame, y=None):
        X = X[self.cols] if self.cols else X
        self.cols = self.cols or X.columns

        q1 = X.quantile(0.25, interpolation=self.interpolation)
        q3 = X.quantile(0.75, interpolation=self.interpolation)
        self.q2 = X.quantile(0.5, interpolation=self.interpolation)
        self.iqr = q3 - q1
        return self

    def transform(self, X: pd.DataFrame, y=None):
        check_is_fitted(self, 'iqr')
        q2, iqr, m = self.q2, self.iqr, self.multiplier
        x = X.copy()
        for col in self.cols:
            if col not in x:
                msg = 'Column {} is not found in the DataFrame'.format(col)
                if self.error == 'raise':
                    raise ValueError(msg)
                if self.error == 'warn':
                    warnings.warn(msg)

            lower_bound = q2[col] - m * iqr[col]
            upper_bound = q2[col] + m * iqr[col]
            x.loc[x[col] > upper_bound, col] = upper_bound
            x.loc[x[col] < lower_bound, col] = lower_bound
        return x


class QuantileOutlierRemover(BaseEstimator, TransformerMixin):
    """ Removing outlier based on skewness threshold """
    
    def __init__(self, skewness_threshold=0.8, outlier_quantile=0.1, cols=None, interpolation='nearest', error='warn'):
        """
        :param skewness_threshold: the skewness limit above or below which 
        :param outlier_quantile: the percentage of data to be treated as outlier
        :param interpolation: interpolation used in calculating the quantile
        :param cols: A list of column names to apply transformations, default for all the numerical columns
        :param error: Specify the action when the DataFrame passed to transform doesn't have all the columns,
            supported actions are ['raise', 'ignore', 'warn']
        """
        self.skewness_threshold = skewness_threshold
        self.outlier_quantile = outlier_quantile
        self.interpolation = interpolation
        self.cols = cols
        self.error = error

        self.upper_threshold = None
        self.lower_threshold = None

    def fit(self, X: pd.DataFrame, y=None):
        self.cols = cols = self.cols or X.select_dtypes(include='number').columns.tolist()
        self.skewness = skewness = pd.Series(skew(X[cols]), index=cols)
        self.pos_skew_cols = pos_skew_cols = skewness[skewness > self.skewness_threshold].index.tolist()
        self.neg_skew_cols = neg_skew_cols = skewness[skewness < -self.skewness_threshold].index.tolist()

        if self.pos_skew_cols:
            self.upper_threshold = upper_threshold = X[pos_skew_cols].quantile(1-self.outlier_quantile, 
                                                                               interpolation=self.interpolation)
        if self.neg_skew_cols:
            self.lower_threshold = lower_threshold = X[neg_skew_cols].quantile(self.outlier_quantile, 
                                                                               interpolation=self.interpolation)
        return self
    
    def transform(self, X: pd.DataFrame, y=None):
        check_is_fitted(self, 'pos_skew_cols')
        X = X.copy()
        pos_skew_cols = [c for c in X.columns if c in self.pos_skew_cols]
        neg_skew_cols = [c for c in X.columns if c in self.neg_skew_cols]
        
        upper_threshold, lower_threshold = self.upper_threshold, self.lower_threshold
        for col in pos_skew_cols:
            X.loc[X[col] > upper_threshold[col], col] = upper_threshold[col]
        for col in neg_skew_cols:
            X.loc[X[col] < lower_threshold[col], col] = lower_threshold[col]
        return X


class OrdinalEncoder(BaseEstimator, TransformerMixin):
    """ Similar Scikit-Learn OrdinalEncoder but allows for arbitrary ordering in the columns,
        also handles unseen values during transform() process.
    """
    def __init__(self, cols=None, fill=True, error='warn', unseen='warn'):
        """
        :param cols: A list of column names to apply transformations, default for all the columns
        :param fill: Whether to fill missing value before encoding
        :param error: Specify the action when the DataFrame passed to transform doesn't have all the columns,
            supported actions are ['raise', 'ignore', 'warn']
        :param unseen: Specify the action when encountered with unseen values,
            supported actions are ['raise, 'silent', 'warn']
        """
        if isinstance(cols, str):
            self.cols = [cols]
        else:
            self.cols = cols
        self.fill = fill
        self.error = error
        self.unseen = unseen

    def fit(self, X: pd.DataFrame, y=None):
        X = X[self.cols] if self.cols else X
        if not self.fill:
            assert_all_finite(X, allow_nan=False)
        else:
            X = X.copy().fillna('_MISSING')
        self.categories_ = dict()

        for col in X:
            cutoff = _encode_python(X[col].astype(str))
            self.categories_[col] = cutoff
        return self

    def transform(self, X: pd.DataFrame, y=None):
        check_is_fitted(self, 'categories_')
        x = X.copy()

        for col in self.cols:
            if col not in x:
                msg = 'Column {} is not found in the DataFrame'.format(col)
                if self.error == 'raise':
                    raise ValueError(msg)
                if self.error == 'warn':
                    warnings.warn(msg)

            if not self.fill:
                assert_all_finite(x[col], allow_nan=False)
            else:
                x[col] = x[col].fillna('_MISSING').astype(str)
            cutoff = self.categories_[col]
            _, x[col] = _encode_python(x[col], uniques=cutoff, encode=True, unseen=self.unseen)
        return x


class CorrelationRemover(BaseEstimator, TransformerMixin):

    def __init__(self, cols=None, categorical_cols=None, threshold=0.8, method='pearson', save_corr=False):
        """
        :param cols: A list of feature names, sorted by importance from high to low
        :param categorical_cols: A list of categorical column names which will all be kept at the moment
        :param threshold: The correlation upper bound
        :param method: The method used for calculating correlation
        :param save_corr: Whether to save the correlation matrix
        """
        self.cols = cols
        self.categorical_cols = categorical_cols or list()
        self.threshold = threshold
        self.method = method
        self.save_corr = save_corr
        self.num_corr_mat = None
        self.cat_corr_mat = None

        self.drop_cols = None

    @staticmethod
    def cat_corr_matrix(X):
        n = X.shape[1]
        col_names = X.columns.tolist()
        corr_mat = np.empty((n, n))
        
        def cat_corr(s1: pd.Series, s2: pd.Series):
            return (s1.fillna('_MISSING_')==s2.fillna('_MISSING_')).mean()
        
        for i in range(n):
            for j in range(i+1):
                if i == j:
                    corr_mat[i][j] = 1
                corr_mat[i][j] = corr_mat[j][i] = cat_corr(X[col_names[i]], X[col_names[j]])
        return pd.DataFrame(corr_mat, index=col_names, columns=col_names)

    def fit(self, X, y=None, **fit_params):
        """ Return the number of dropped columns """
        self.cols = cols = self.cols or X.columns.tolist()
        _error_cols = set(cols) - set(X.columns)
        if _error_cols:
            raise ValueError('The following columns does not exist in DataFrame X: ' +
                             repr(list(_error_cols)))

        numerical_cols = list(set(cols) - set(self.categorical_cols))
        # make sure the categorical column actually exist in DataFrame X
        categorical_cols = self.categorical_cols or X.select_dtypes(include=['object']).columns.tolist()
        categorical_cols = [c for c in categorical_cols if c in cols]
        self.categorical_cols = categorical_cols

        self.drop_cols = list()

        if numerical_cols:
            num_corr_mat = X[numerical_cols].corr(method=self.method).abs()
            
            for i, c_a in enumerate(numerical_cols):
                for j in range(i+1, len(numerical_cols)):
                    c_b = numerical_cols[j]
                    if c_b not in self.drop_cols and \
                        num_corr_mat.loc[c_a, c_b] > self.threshold:
                            self.drop_cols.append(c_b)
            if self.save_corr:
                self.num_corr_mat = num_corr_mat

        if categorical_cols:
            cat_corr_mat = self.cat_corr_matrix(X[categorical_cols]).abs()
            
            for i, c_a in enumerate(categorical_cols):
                for j in range(i+1, len(categorical_cols)):
                    c_b = categorical_cols[j]
                    if c_b not in self.drop_cols and \
                        cat_corr_mat.loc[c_a, c_b] > self.threshold:
                            self.drop_cols.append(c_b)
        
            if self.save_corr:
                self.cat_corr_mat = cat_corr_mat
                        
        self.keep_cols = [c for c in cols if c not in self.drop_cols]
        return self

    def transform(self, X, y=None):
        if self.drop_cols is None:
            raise NotFittedError('This CorrelationRemover is not fitted. Call the fit method first.')
        # drop_cols = set(X.columns) & set(self.drop_cols)
        return X[self.keep_cols]


if __name__ == '__main__':
    import random
    import numpy as np

    X = pd.DataFrame({'a': list(range(1000)),
                      'b': [random.randint(5, 10) for _ in range(1000)],
                      'c': [random.randint(1, 100) for _ in range(1000)]})
    Encoder = QuantileOutlierRemover(cols=['a', 'b'])
    print(Encoder.fit_transform(X))
