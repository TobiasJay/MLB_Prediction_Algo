import pandas as pd
import numpy as np
import os

from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn import metrics


def main():
    # Read the CSV file into a pandas DataFrame
    p_df = pd.read_csv('data/pitcherstats.csv')
    b_df = pd.read_csv('data/batterstats.csv')

    # Extract the required columns
    # Opp_R = Opponent Runs while pitcher was in the game
    pitcher_columns = ['Date', 'Player-additional', 'IP', 'Opp_R', 'ER', 'Team', 'Opp', 'Result'] # add more features later
    selected_pdata = p_df[pitcher_columns]
    batter_columns = ['Date', 'BA', 'Team', 'Opp', 'Result'] # add more features later (HR, RBI, etc.)
    selected_bdata = b_df[batter_columns]

    # Create seasonal avg BA column
    # Create Opp Pitcher ERA column
    # Create Score column

    # Create seasonal avg BA column
    # Doesn't include current BA value in the average
    X1 = pd.DataFrame(selected_bdata['Date'])
    X1['BA_AvgToDate'] = (selected_bdata.groupby('Team')['BA'].cumsum() - selected_bdata['BA']) / (selected_bdata.groupby('Team').cumcount())
    # adding column for average of BA over last 5 games
    window_size = 5

    
    # Calculate the rolling mean over the last five games (Change window function in x.rolling(window= ... )) Check documentation
    # Find x.rolling documentation at this URL: https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.rolling.html
    # closed='left' means that the window will not include the current game
    X1['BA_AvgLast5'] = selected_bdata.groupby('Team')['BA'].transform(lambda x: x.rolling(window=window_size, min_periods=1,closed='left').mean())
    X1['Team'] = selected_bdata['Team']
    # Map IP to 0.0, 0.3333, 0.6667 for the ERA math to work (original values have 4.1 represent 4 innings and 1 out)
    selected_pdata['IP'] = selected_pdata['IP'].apply(lambda x: int(x) + 1/3 if round(x % 1, 1) == 0.1 else int(x) + 2/3 if round(x % 1, 1) == 0.2 else x)

    X2 = pd.DataFrame(selected_pdata['Date'])

    # ERA is today's ER / today's IP, IP total is all IP seasonally, ERA_cum is ERA up to, but not including today
    X2['IP TOTAL'] = selected_pdata.groupby(['Player-additional'])['IP'].cumsum()
    X2['ERA'] = 9 * selected_pdata['ER'] / selected_pdata['IP']
    X2['ERA_cum'] = 9 * (selected_pdata.groupby(['Player-additional'])['ER'].cumsum() - selected_pdata['ER']) / (selected_pdata.groupby(['Player-additional'])['IP'].cumsum() - selected_pdata['IP'])
    X2['Player-additional'] = selected_pdata['Player-additional']


    # Calculate the rolling mean over the last five games
    # does not include today's ERA in calcuation
    X2['IP_Last5'] = selected_pdata.groupby(['Player-additional'])['IP'].transform(lambda x: x.rolling(window=window_size, min_periods=1,closed='left').sum())
    X2['ER_Last5'] = selected_pdata.groupby(['Player-additional'])['ER'].transform(lambda x: x.rolling(window=window_size, min_periods=1,closed='left').sum())
    X2['ERA_Last5'] = 9 * X2['ER_Last5'] / X2['IP_Last5']
    # Using a trick here to link the opposing pitchers and the batters together
    X2['Team'] = selected_pdata['Opp']
    print(X2.head(200))
    # Batting and pitching datasets are not lined up, so we need to merge them, but merging wasn't working earlier

    # Issue: there are double headers and so sometimes there are multiple games on the same day. Who pitches which game?
    


    X1.drop_duplicates(subset=['Date', 'Team'], keep='first', inplace=True)
    matches = pd.merge(X1, X2, how='inner', on=['Date', 'Team'])
    matches.drop(['IP_Last5', 'ER_Last5'], axis=1, inplace=True)
    # check for duplicate rows in pd.merge
    # Team and result will match but pitcher will be from opposing team
    matches['Result'] = selected_bdata['Result']
    # Extract win/loss and scores
    matches[['Outcome', 'Scores']] = matches['Result'].str.extract(r'([WL]) (\d+-\d+)')

    # Create binary column for win (1) and loss (0)
    matches['Win'] = (matches['Outcome'] == 'W').astype(int)

    # Split the Scores column into two separate columns
    matches[['Score', 'Opp_Score']] = matches['Scores'].str.split('-', expand=True).astype(int)

    # Drop unnecessary columns
    matches = matches.drop(['Result', 'Outcome', 'Scores', 'Opp_Score', 'ERA', 'Player-additional','Team','IP TOTAL','Win'], axis=1)
    # Drop rows with NaN values
    matches.dropna(inplace=True)
    
    # drop target from X and save to y
    y = matches['Score']
    X = matches.drop(['Score'], axis=1)

    # Create Training and test sets
    # Line 4016 in dataset marks the start of september, the last month of the season
    # Originally 4016 was the start of september, but we removed rows with NaN values, so the split is now at 3611
    X_train = X.head(3611)
    X_test = X.tail(len(X) - 3611)
    y_train = y.head(3611)
    y_test = y.tail(len(y) - 3611)
    # Then we need to split into features and target (# of runs scored)
    print(X_train)
    print(X_test)


if __name__ == '__main__':
    main()