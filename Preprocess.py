import pandas as pd
import numpy as np


def trunc_split(data, train_size, test_size):
    if len(data) < train_size + test_size:
        raise ValueError('row must be less than the length of the dataset')

    data_train = data.head(train_size)
    train_and_test = data.head(train_size + test_size)
    data_test = train_and_test.tail(len(train_and_test) - train_size)
    return data_train, data_test


# Performs preprocessing on the datasets and returns the X and y datasets ready for use in modelling
def split(data, row):
    if len(data) < row:
        raise ValueError('row must be less than the length of the dataset')

    data_train = data.head(row)
    data_test = data.tail(len(data) - row)
    return data_train, data_test


def preprocess(p_df, b_df):
    # Extract the required columns
    # Opp_R = Opponent Runs while pitcher was in the game
    pitcher_columns = ['Date', 'Player-additional', 'IP', 'Opp_R', 'ER', 'Team', 'Opp', 'Result', 'Unnamed: 5'] # add more features later
    selected_pdata = p_df[pitcher_columns]
    batter_columns = ['Date', 'BA', 'Team', 'Opp', 'Result', 'Unnamed: 3', 'OPS'] # add more features later (HR, RBI, etc.)
    selected_bdata = b_df[batter_columns]


    # Initialize empty DataFrame for batters and save date for reference
    batters = pd.DataFrame(selected_bdata['Date'])
    batters['Opp'] = selected_bdata['Opp']
    batters['HorA'] = selected_bdata['Unnamed: 3'] # Finds the column indicating who is @ home
    # Doesn't include current BA value in the average (due to the subtraction of BA))
    batters['OPS_AvgToDate'] = (selected_bdata.groupby('Team')['OPS'].cumsum() - selected_bdata['OPS']) / (selected_bdata.groupby('Team').cumcount())
    

    # Changed the window to 4 games and the weights to 0.4, 0.3, 0.2, 0.1
    # Based this paper on the weights: ah i forgot couldn't find it, lets see if this helps at all
    # Looking at output graphs it certainly seems to help, especially on converging to positive values quickly
    window_size = 4

    # Calculate the rolling mean over the last five games (Change window function in x.rolling(window= ... )) Check documentation
    # Find x.rolling documentation at this URL: https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.rolling.html
    # right now its set to an integer so its just a flat average of the last 5 games
    # closed='left' means that the window will not include the current game

    weights = np.array([0.4, 0.3, 0.2, 0.1])

    def weighted_average(x):
        return np.sum(x * weights[:len(x)]) / np.sum(weights[:len(x)])

    # Old last 5 games calculation:
    # batters['OPS_AvgLast5'] = selected_bdata.groupby('Team')['OPS'].transform(lambda x: x.rolling(window=window_size, min_periods=1,closed='left').mean())

    batters['OPS_AvgLast5'] = selected_bdata.groupby('Team')['OPS'].transform(lambda x: x.rolling(window=window_size, min_periods=1,closed='left').apply(weighted_average, raw=False))
    batters['Team'] = selected_bdata['Team']


    # Map IP to 0.0, 0.3333, 0.6667 for the ERA math to work (original values have 4.1 represent 4 innings and 1 out)
    selected_pdata['IP'] = selected_pdata['IP'].apply(lambda x: int(x) + 1/3 if round(x % 1, 1) == 0.1 else int(x) + 2/3 if round(x % 1, 1) == 0.2 else x)

    # Initialize empty DataFrame for pitchers and save date for reference
    pitchers = pd.DataFrame(selected_pdata['Date'])
    pitchers['Team'] = selected_pdata['Team']
    pitchers['Opp'] = selected_pdata['Opp']

    # ERA is today's ER / today's IP, IP total is all IP seasonally, ERA_cum is ERA up to, but not including today
    pitchers['IP TOTAL'] = selected_pdata.groupby(['Player-additional'])['IP'].cumsum()
    pitchers['ERA'] = 9 * selected_pdata['ER'] / selected_pdata['IP']
    pitchers['ERA_cum'] = 9 * (selected_pdata.groupby(['Player-additional'])['ER'].cumsum() - selected_pdata['ER']) / (selected_pdata.groupby(['Player-additional'])['IP'].cumsum() - selected_pdata['IP'])
    pitchers['Player-additional'] = selected_pdata['Player-additional']


    def weighted_sum(x):
        return np.sum(x * weights[:len(x)])
    # Calculate the rolling mean over the last five games
    # does not include today's ERA in calcuation
    # Old last 5 games calculation:
    #pitchers['IP_Last5'] = selected_pdata.groupby(['Player-additional'])['IP'].transform(lambda x: x.rolling(window=window_size, min_periods=1,closed='left').sum())
    #pitchers['ER_Last5'] = selected_pdata.groupby(['Player-additional'])['ER'].transform(lambda x: x.rolling(window=window_size, min_periods=1,closed='left').sum())

    pitchers['IP_Last5'] = selected_pdata.groupby(['Player-additional'])['IP'].transform(lambda x: x.rolling(window=window_size, min_periods=1,closed='left').apply(weighted_sum, raw=False))
    pitchers['ER_Last5'] = selected_pdata.groupby(['Player-additional'])['ER'].transform(lambda x: x.rolling(window=window_size, min_periods=1,closed='left').apply(weighted_sum, raw=False))
    pitchers['ERA_Last5'] = 9 * pitchers['ER_Last5'] / pitchers['IP_Last5']
    pitchers.drop(['IP_Last5', 'ER_Last5'], axis=1, inplace=True)

    # Merge pitchers and batters together into one dataframe, need to drop duplicates from batters aka batters because there are some games with no starting pitcher
    batters.drop_duplicates(subset=['Date', 'Team'], keep='first', inplace=True)
    batters['Result'] = selected_bdata['Result'] # Result for pitchers is different than game result for the team, so we get result from batting dataset
    matches = pd.merge(batters, pitchers, how='inner', on=['Date', 'Team','Opp'])


    # Initialize empty DataFrame for new dataset that condenses each game into a single row (original dataset has a row for each team so two per game)
    game_pairs = pd.DataFrame()

    # Iterate through unique dates in the original DataFrame
    for date in matches['Date'].unique():
        # Subset the DataFrame for the current date
        subset_df = matches[matches['Date'] == date]
        # Iterate through rows to isolate pairs of games
        for index, row in subset_df.iterrows():
            # Find the corresponding row with the opposing team and only keep the rows for teams that played away. (aka with the @ symbol)

            opposing_row = subset_df[(subset_df['Team'] == row['Opp']) & (row['HorA'] == '@')]
            # Check if an opposing row is found
            if not opposing_row.empty:
                # Away = row, Home = opposing_row
                combined_row = {
                    'Date': date,
                    'AwayTeam': row['Team'],
                    'HomeTeam': opposing_row['Team'].values[0],
                    'HomeResult': opposing_row['Result'].values[0],
                    'H_OPS_AvgToDate': opposing_row['OPS_AvgToDate'].values[0],
                    'A_OPS_AvgToDate': row['OPS_AvgToDate'],
                    'H_OPS_AvgLast5': opposing_row['OPS_AvgLast5'].values[0],
                    'A_OPS_AvgLast5': row['OPS_AvgLast5'],
                    'H_ERA_cum': opposing_row['ERA_cum'].values[0],
                    'A_ERA_cum': row['ERA_cum'],
                    'H_ERA_Last5': opposing_row['ERA_Last5'].values[0],
                    'A_ERA_Last5': row['ERA_Last5'],
                }                
                # Append the combined row to the DataFrame
                game_pairs = game_pairs._append(combined_row, ignore_index=True)


    # Change the result column to a binary column for win (1) and loss (0) as well as keeping the scores
    # Extract win/loss and scores
    game_pairs[['Outcome', 'Scores']] = game_pairs['HomeResult'].str.extract(r'([WL]) (\d+-\d+)')

    # Create binary column for win (1) and loss (0) for the home team
    game_pairs['H_Win'] = (game_pairs['Outcome'] == 'W').astype(int)

    # Split the Scores column into two separate columns for home and away scores
    game_pairs[['H_Score', 'A_Score']] = game_pairs['Scores'].str.split('-', expand=True).astype(int)
    
    # Drop unnecessary columns
    game_pairs.drop(['HomeResult', 'Outcome', 'Scores'], axis=1, inplace=True)

    # Drop rows with NaN values
    # This effectively eliminates data from our dataset, but our other options for sourcing data were not viable for our timeframe
    game_pairs.dropna(inplace=True)
    # drop target from X and save to y
    y = game_pairs['H_Win']
    X = game_pairs.drop(['H_Score', 'A_Score', 'Date', 'AwayTeam','HomeTeam','H_Win'], axis=1)
    return X, y
    
