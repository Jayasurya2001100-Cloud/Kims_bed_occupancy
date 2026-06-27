import argparse
from datetime import timedelta
import numpy as np
import pandas as pd

try:
    from lightgbm import LGBMRegressor
except Exception:
    LGBMRegressor = None

try:
    from xgboost import XGBRegressor
except Exception:
    XGBRegressor = None

try:
    from prophet import Prophet
except Exception:
    Prophet = None

from sklearn.ensemble import RandomForestRegressor

import matplotlib.pyplot as plt


def make_features(series, date_index, max_lag=7):
    """Create a DataFrame of features from a pandas Series indexed by date."""
    df = pd.DataFrame({'date': date_index, 'y': series}).set_index('date')
    for lag in range(1, max_lag + 1):
        df[f'lag_{lag}'] = df['y'].shift(lag)
    df['rolling_7'] = df['y'].rolling(7).mean()
    df['dayofweek'] = df.index.dayofweek
    df['day'] = df.index.day
    df['month'] = df.index.month
    return df


def train_ensemble(X, y):
    models = []
    if LGBMRegressor is not None:
        m = LGBMRegressor(random_state=42)
        m.fit(X, y)
        models.append(m)
    if XGBRegressor is not None:
        m = XGBRegressor(random_state=42, verbosity=0)
        m.fit(X, y)
        models.append(m)
    # fallback / stability model
    rf = RandomForestRegressor(n_estimators=200, random_state=42)
    rf.fit(X, y)
    models.append(rf)
    return models


def ensemble_predict(models, X):
    preds = np.column_stack([m.predict(X) for m in models])
    return preds.mean(axis=1)


def iterative_forecast(initial_series, last_date, models, horizon=90):
    """Given a pandas Series of historical daily values (indexed by date),
    iteratively forecast `horizon` days after last_date using recursive features."""
    series = initial_series.copy().sort_index()
    preds = []
    current_date = last_date
    for i in range(horizon):
        next_date = current_date + timedelta(days=1)
        # build features for next_date using series
        idx = pd.date_range(end=next_date, periods=8)  # enough to get lags
        sub = series.reindex(idx)
        # get lag values
        lags = [sub.iloc[-(lag + 1)] if len(sub.dropna()) >= lag else np.nan for lag in range(1, 8)]
        # Prepare a single-row DataFrame with same columns
        feat = {
            'lag_1': lags[0],
            'lag_2': lags[1],
            'lag_3': lags[2],
            'lag_4': lags[3],
            'lag_5': lags[4],
            'lag_6': lags[5],
            'lag_7': lags[6],
            'rolling_7': sub[-7:].mean(),
            'dayofweek': next_date.dayofweek,
            'day': next_date.day,
            'month': next_date.month,
        }
        X_next = pd.DataFrame([feat])
        # if any NaN in X_next, replace with zeros (conservative)
        X_next = X_next.ffill().fillna(0)
        pred = ensemble_predict(models, X_next)[0]
        preds.append((next_date, pred))
        # append prediction to series for future lag calculations
        series.loc[next_date] = pred
        current_date = next_date
    return pd.Series({d: v for d, v in preds})


def main(args):
    df = pd.read_csv(args.input)
    if 'date' not in df.columns:
        raise SystemExit('Input CSV must contain a `date` column')
    # ensure date
    df['date'] = pd.to_datetime(df['date'])
    if 'occupied_beds' not in df.columns:
        # try to infer a beds column
        candidates = [c for c in df.columns if 'bed' in c.lower() or 'occup' in c.lower()]
        if not candidates:
            raise SystemExit('Input CSV must contain an `occupied_beds` column')
        df = df.rename(columns={candidates[0]: 'occupied_beds'})

    daily = df.groupby('date', as_index=False)['occupied_beds'].sum()
    daily = daily.set_index('date').asfreq('D').ffill()

    last_date = daily.index.max()

    compare_days = args.compare_days
    train_days = args.train_days
    forecast_horizon = args.forecast_days

    # define windows
    compare_start = last_date - timedelta(days=compare_days - 1)
    training_end = compare_start - timedelta(days=1)
    training_start = training_end - timedelta(days=train_days - 1)

    # ensure bounds
    if training_start < daily.index.min():
        training_start = daily.index.min()

    train_series = daily['occupied_beds'].loc[training_start:training_end]

    # build features for training
    # Prefer Prophet for robust time-series forecasting when available
    if Prophet is not None:
        # Prepare data for Prophet
        prop_df = daily.reset_index().rename(columns={'date': 'ds', 'occupied_beds': 'y'})

        # Train up to training_end to generate comparison forecasts
        prop_train = prop_df[prop_df['ds'] <= training_end]
        m = Prophet(yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False)
        m.fit(prop_train)

        comp_future = m.make_future_dataframe(periods=compare_days, freq='D')
        comp_pred = m.predict(comp_future)
        comp_pred = comp_pred.set_index('ds')
        comp_pred = comp_pred.loc[training_end + timedelta(days=1):training_end + timedelta(days=compare_days)]
        comp_df = pd.DataFrame({'date': comp_pred.index, 'forecast': comp_pred['yhat'].values}).set_index('date')
        comp_df['actual'] = daily['occupied_beds'].reindex(comp_df.index)
        comp_df['abs_error'] = (comp_df['actual'] - comp_df['forecast']).abs()
        comp_df['error_pct'] = (comp_df['abs_error'] / comp_df['actual'].replace(0, np.nan)) * 100

        # Retrain on recent window up to last_date and forecast future horizon
        prop_fut_train = prop_df[prop_df['ds'] <= last_date]
        m2 = Prophet(yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False)
        m2.fit(prop_fut_train)
        fut_future = m2.make_future_dataframe(periods=forecast_horizon, freq='D')
        fut_pred = m2.predict(fut_future)
        fut_pred = fut_pred.set_index('ds')
        future_pred = fut_pred.loc[last_date + timedelta(days=1): last_date + timedelta(days=forecast_horizon)]
        future_df = pd.DataFrame({'date': future_pred.index, 'forecast': future_pred['yhat'].values}).set_index('date')
    else:
        # fallback to ensemble approach
        df_feats = make_features(daily['occupied_beds'], daily.index)
        train_df = df_feats.loc[training_start:training_end].dropna()
        X_train = train_df.drop(columns=['y'])
        y_train = train_df['y']

        models = train_ensemble(X_train, y_train)

        # produce comparison forecasts for the compare window (iterative from training_end)
        comp_preds = iterative_forecast(daily['occupied_beds'].loc[:training_end], training_end, models, horizon=compare_days)
        comp_df = pd.DataFrame({'date': comp_preds.index, 'forecast': comp_preds.values})
        comp_df = comp_df.set_index('date')
        comp_df['actual'] = daily['occupied_beds'].reindex(comp_df.index)
        comp_df['abs_error'] = (comp_df['actual'] - comp_df['forecast']).abs()
        comp_df['error_pct'] = (comp_df['abs_error'] / comp_df['actual'].replace(0, np.nan)) * 100

        # Retrain on most recent `train_days` up to last_date for future forecast as requested
        fut_train_start = last_date - timedelta(days=train_days - 1)
        if fut_train_start < daily.index.min():
            fut_train_start = daily.index.min()
        fut_train_df = df_feats.loc[fut_train_start:last_date].dropna()
        X_fut = fut_train_df.drop(columns=['y'])
        y_fut = fut_train_df['y']
        fut_models = train_ensemble(X_fut, y_fut)

        future_preds = iterative_forecast(daily['occupied_beds'].loc[:last_date], last_date, fut_models, horizon=forecast_horizon)
        future_df = pd.DataFrame({'date': future_preds.index, 'forecast': future_preds.values}).set_index('date')

    # Save Excel with two sheets
    writer = pd.ExcelWriter(args.output_excel, engine='openpyxl')
    comp_df.reset_index().to_excel(writer, sheet_name='last_month_comparison', index=False)
    future_df.reset_index().to_excel(writer, sheet_name='future_forecast', index=False)
    writer.close()

    # Plot last month comparison
    plt.figure(figsize=(10, 5))
    plt.plot(comp_df.index, comp_df['actual'], label='Actual', marker='o')
    plt.plot(comp_df.index, comp_df['forecast'], label='Forecast', marker='x')
    plt.legend()
    plt.title('Actual vs Forecast — Last Month')
    plt.xlabel('Date')
    plt.ylabel('Occupied beds')
    plt.tight_layout()
    plt.savefig(args.output_plot)

    print('Saved comparison and forecast:')
    print(f' - Excel: {args.output_excel}')
    print(f' - Plot:  {args.output_plot}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='hospital_enhanced_full_dataset.csv')
    parser.add_argument('--output-excel', default='forecast_report.xlsx')
    parser.add_argument('--output-plot', default='forecast_last_month.png')
    parser.add_argument('--train-days', type=int, default=90, help='Number of days to train on (default 90)')
    parser.add_argument('--compare-days', type=int, default=30, help='Days to compare actual vs forecast (default 30)')
    parser.add_argument('--forecast-days', type=int, default=90, help='Days to forecast ahead (default 90)')
    args = parser.parse_args()
    main(args)
