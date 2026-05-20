import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from Transactions import TransactionList,Transaction
import io
import base64


#the make_seaborn_... functions return graphs as strings of html image tags
#as well as the image
#those are later used is Reader.py to store the images in the excel report file


def make_seaborn_graph_daily(transactions: TransactionList)->tuple[str,io.BytesIO]:
    # build dataframe with day and amount
    df = pd.DataFrame([{'date': t.date, 'amount': abs(t.amount)} for t in transactions.transactions if t.amount<=0])
    if df.empty:
        return None

    # ensure date column is datetime64 (important to use .dt)
    df['date'] = pd.to_datetime(df['date'])

    # aggregate daily totals and create a formatted label column (string)
    daily_totals_df = df.groupby('date', as_index=False)['amount'].sum().sort_values('date')
    daily_totals_df['date_label'] = daily_totals_df['date'].dt.strftime('%Y-%m-%d')

    # plot: use date_label as categorical x to avoid .dt in ticklabels
    fig, ax = plt.subplots(figsize=(14, 6))
    sns.barplot(x='date_label', y='amount', data=daily_totals_df, ax=ax, hue='date_label', legend=False)
    ax.set_title('Daily Transaction Totals')
    
    ax.set_xlabel('Date')
    ax.set_ylabel('Amount')
    plt.xticks(rotation=45)
    plt.tight_layout()

   

    # save to buffer and return an <img> tag with base64
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    plot_data = base64.b64encode(buf.getvalue()).decode('utf-8')
    html_img_tag = f'<img src="data:image/png;base64, {plot_data}" alt="Daily Transaction Graph">'

    return html_img_tag,buf

def make_seaborn_graph_monthly(transactions: TransactionList)->tuple[str,io.BytesIO]:
    # dataframe with date and amount
    df = pd.DataFrame([{'date': t.date, 'amount': abs(t.amount)} for t in transactions.transactions if t.amount<=0])
    if df.empty:
        return None

    df['date'] = pd.to_datetime(df['date'])

    # group by month, sum amounts
    monthly = df.groupby(df['date'].dt.to_period('M'))['amount'].sum().reset_index()
    # convert Period to timestamp for formatting
    monthly['date'] = monthly['date'].dt.to_timestamp()
    monthly['month_label'] = monthly['date'].dt.strftime('%Y-%m')

    fig, ax = plt.subplots(figsize=(14, 6))
    sns.barplot(x='month_label', y='amount', data=monthly, ax=ax, hue='month_label', legend=False)
    ax.set_title('Monthly Transaction Totals')
    ax.set_xlabel('Month')
    ax.set_ylabel('Amount')
    plt.xticks(rotation=45)
    plt.tight_layout()

  

    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')   # bbox_inches trims extra margins

    plt.close(fig)
    plot_data = base64.b64encode(buf.getvalue()).decode('utf-8')
    html_img_tag=f'<img src="data:image/png;base64,{plot_data}" alt="Monthly Transaction Graph" />',
    return html_img_tag,buf

def make_seaborn_pie_chart(transactions: TransactionList)->tuple[str,io.BytesIO]:
    #dataframe with category and amount
    #any time period is fine since we are grouping by category
    df=pd.DataFrame([{'category': t.category,'amount': abs(t.amount)} for t in transactions.transactions if t.amount<=0])  # only include transactions with a category
    if df.empty:
        return None
    categorised=df.groupby(df['category'])['amount'].sum().reset_index()

    # convert to absolute values so pie shows magnitudes regardless of sign
    categorised['amount'] = categorised['amount'].abs()

    # choose a bold palette instead of very light pastels
    colors = sns.color_palette('pastel')[0:len(categorised)]

    fig,ax=plt.subplots(figsize=(8,8))
    labels=categorised['category']

    wedges,texts,autotexts=ax.pie(
        categorised['amount'],
        labels=None,             
        colors=colors,
        autopct='%1.1f%%',       
        pctdistance=0.75,         
        startangle=140,
    )

    ax.legend(wedges,labels,title='Amount by category',loc='center left',bbox_to_anchor=(1,0,0.5,1))

  

    buf=io.BytesIO()
    fig.savefig(buf,format='png',bbox_inches='tight')
    plt.close(fig)
    plot_data=base64.b64encode(buf.getvalue()).decode('utf-8')
    html_img_tag= f'<img src="data:image/png;base64,{plot_data}" alt="Categories Transaction Graph" />'
    return html_img_tag,buf
