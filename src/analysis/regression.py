"""
多元回归与驱动因子分析模块
===========================
量化气候变化（降雨、气温）、人类活动（土地利用变化）等驱动因子
对松辽流域河道变迁与植被响应的综合影响。

支持：
  1. 普通多元线性回归（OLS）
  2. 逐步回归（特征选择）
  3. 相关性矩阵与热力图

用法示例
--------
>>> from src.analysis.regression import DriversAnalysis
>>> da = DriversAnalysis()
>>> model = da.fit(X_df, y_series)
>>> da.print_summary(model)
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


class DriversAnalysis:
    """
    驱动因子多元回归分析器。

    Examples
    --------
    构造驱动因子数据框 X（行=年份，列=驱动变量），
    响应变量 y（如年均 NDVI 或河道面积），然后调用 fit()。
    """

    def __init__(self) -> None:
        self._model = None
        self._feature_names: List[str] = []

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        standardize: bool = True,
    ) -> "DriversAnalysis":
        """
        拟合多元线性回归模型。

        Parameters
        ----------
        X : pd.DataFrame  驱动因子（列 = 变量名，行 = 年份）
        y : pd.Series  响应变量（如年均 NDVI 均值）
        standardize : bool  是否标准化特征（Z-score），便于比较系数大小

        Returns
        -------
        self
        """
        from sklearn.linear_model import LinearRegression
        from sklearn.preprocessing import StandardScaler

        self._feature_names = list(X.columns)
        X_arr = X.values.astype(float)
        y_arr = y.values.astype(float)

        # 去除含 NaN 的行
        valid = ~(np.isnan(X_arr).any(axis=1) | np.isnan(y_arr))
        X_valid, y_valid = X_arr[valid], y_arr[valid]

        if standardize:
            self._scaler = StandardScaler()
            X_valid = self._scaler.fit_transform(X_valid)
        else:
            self._scaler = None

        self._model = LinearRegression()
        self._model.fit(X_valid, y_valid)
        self._X_valid = X_valid
        self._y_valid = y_valid

        return self

    def summary(self) -> pd.DataFrame:
        """
        返回回归系数摘要表，含标准误差和近似 p 值。

        Returns
        -------
        pd.DataFrame  列：variable, coefficient, std_error, t_stat, p_value
        """
        if self._model is None:
            raise RuntimeError("请先调用 fit() 拟合模型。")

        from scipy import stats

        X = self._X_valid
        y = self._y_valid
        n, k = X.shape

        y_pred = self._model.predict(X)
        residuals = y - y_pred
        mse = (residuals**2).sum() / (n - k - 1)

        # 计算协方差矩阵
        X_with_intercept = np.column_stack([np.ones(n), X])
        try:
            cov = mse * np.linalg.inv(X_with_intercept.T @ X_with_intercept)
        except np.linalg.LinAlgError:
            cov = mse * np.linalg.pinv(X_with_intercept.T @ X_with_intercept)

        coefs = np.concatenate([[self._model.intercept_], self._model.coef_])
        std_errors = np.sqrt(np.diag(cov))
        t_stats = coefs / (std_errors + 1e-12)
        p_values = 2 * (1 - stats.t.cdf(np.abs(t_stats), df=n - k - 1))

        names = ["intercept"] + self._feature_names
        df = pd.DataFrame(
            {
                "variable": names,
                "coefficient": np.round(coefs, 6),
                "std_error": np.round(std_errors, 6),
                "t_stat": np.round(t_stats, 4),
                "p_value": np.round(p_values, 6),
            }
        )
        return df

    def r_squared(self) -> Dict[str, float]:
        """返回 R² 和调整 R²。"""
        if self._model is None:
            raise RuntimeError("请先调用 fit()。")

        from sklearn.metrics import r2_score

        y_pred = self._model.predict(self._X_valid)
        r2 = r2_score(self._y_valid, y_pred)
        n, k = self._X_valid.shape
        adj_r2 = 1 - (1 - r2) * (n - 1) / (n - k - 1)
        return {"r2": round(r2, 4), "adj_r2": round(adj_r2, 4)}

    @staticmethod
    def correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
        """
        计算相关系数矩阵（Pearson）。

        Parameters
        ----------
        df : pd.DataFrame  驱动因子 + 响应变量合并的宽表

        Returns
        -------
        pd.DataFrame  相关系数矩阵
        """
        return df.corr(method="pearson").round(4)

    @staticmethod
    def partial_correlation(
        X: pd.DataFrame,
        y: pd.Series,
    ) -> pd.Series:
        """
        计算各驱动因子与响应变量的偏相关系数。

        Parameters
        ----------
        X : pd.DataFrame  驱动因子
        y : pd.Series  响应变量

        Returns
        -------
        pd.Series  偏相关系数（index = 变量名）
        """
        from sklearn.linear_model import LinearRegression

        partial_corrs = {}
        for col in X.columns:
            other_cols = [c for c in X.columns if c != col]
            if not other_cols:
                partial_corrs[col] = np.nan
                continue

            X_others = X[other_cols].values
            x_col = X[col].values
            y_vals = y.values

            valid = ~(np.isnan(X_others).any(axis=1) | np.isnan(x_col) | np.isnan(y_vals))
            if valid.sum() < 5:
                partial_corrs[col] = np.nan
                continue

            # 残差化
            lr = LinearRegression()
            lr.fit(X_others[valid], x_col[valid])
            res_x = x_col[valid] - lr.predict(X_others[valid])

            lr.fit(X_others[valid], y_vals[valid])
            res_y = y_vals[valid] - lr.predict(X_others[valid])

            from scipy.stats import pearsonr

            r, _ = pearsonr(res_x, res_y)
            partial_corrs[col] = round(r, 4)

        return pd.Series(partial_corrs, name="partial_correlation")
