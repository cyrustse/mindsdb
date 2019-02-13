
import os

import _thread
import uuid
import traceback


from mindsdb.libs.data_types.mindsdb_logger import MindsdbLogger
from mindsdb.libs.helpers.multi_data_source import getDS
from mindsdb.libs.helpers.general_helpers import check_for_updates

from mindsdb.config import CONFIG
from mindsdb.libs.data_types.transaction_metadata import TransactionMetadata
from mindsdb.libs.controllers.transaction import Transaction
from mindsdb.libs.constants.mindsdb import *


from pathlib import Path

class Mind:

    def __init__(self, mind_name, mind_root_folder=CONFIG.MINDSDB_STORAGE_PATH, log_level=CONFIG.DEFAULT_LOG_LEVEL, send_logs=CONFIG.SEND_LOGS, log_url=CONFIG.MINDSDB_SERVER_URL):
        """
        This controller defines the API to a MindsDB 'mind', a mind is an object that can learn and predict from data

        :param mind_name: the name you want to identify this mind with
        :param mind_root_folder: the folder where you want to store this mind or load from
        :param log_level: the desired log level
        :param send_logs: if you want to stream logs to a given server (default: False)
        :param log_url: the server you want to stream logs to for visualization (only if send_logs is TRUE)

        """

        # initialize variables
        self.mind_name = mind_name
        self.mind_root_folder = mind_root_folder
        self.mind_uuid = str(uuid.uuid1())

        # initialize log
        self.log = MindsdbLogger(log_level=log_level, send_logs=send_logs, log_url=log_url, uuid=self.mind_uuid)

        # check for updates
        _thread.start_new_thread(check_for_updates, ())

        # set the mindsdb storage folder
        storage_ok = True  # default state

        # if it does not exist try to create it
        if not os.path.exists(CONFIG.MINDSDB_STORAGE_PATH):
            try:
                self.log.info('{folder} does not exist, creating it now'.format(folder=CONFIG.MINDSDB_STORAGE_PATH))
                path = Path(CONFIG.MINDSDB_STORAGE_PATH)
                path.mkdir(exist_ok=True, parents=True)
            except:
                self.log.info(traceback.format_exc())
                storage_ok = False
                self.log.error('MindsDB storage foldler: {folder} does not exist and could not be created'.format(
                    folder=CONFIG.MINDSDB_STORAGE_PATH))

        # If storage path is not writable, raise an exception as this can no longer be
        if not os.access(CONFIG.MINDSDB_STORAGE_PATH, os.W_OK) or storage_ok == False:
            error_message = '''Cannot write into storage path, please either set the config variable mindsdb.config.set('MINDSDB_STORAGE_PATH',<path>) or give write access to {folder}'''
            raise ValueError(error_message.format(folder=CONFIG.MINDSDB_STORAGE_PATH))




    def export(self, model_zip_file):
        """
        If you want to export this mind to a file
        :param model_zip_file: this is the full_path where you want to store a mind to, it will be a zip file

        :return: bool (True/False) True if mind was exported successfully
        """
        pass


    def load(self, model_zip_file):
        """
        If you want to import a mind from a file

        :param model_zip_file: this is the full_path that contains your mind
        :return: bool (True/False) True if mind was importerd successfully
        """
        pass

    def update(self, from_data):
        """
        Use this if you have new data that you want your mind object to learn from

        :param from_data: the data that you want to learn from, this can be either a file, a pandas data frame, or url to a file

        :return:
        """

        pass

    def learn(self, columns_to_predict, from_data = None,  test_from_data=None, group_by = None, window_size = MODEL_GROUP_BY_DEAFAULT_LIMIT, order_by = [], sample_margin_of_error = CONFIG.DEFAULT_MARGIN_OF_ERROR, sample_confidence_level = CONFIG.DEFAULT_CONFIDENCE_LEVEL, breakpoint = PHASE_END, ignore_columns = [], rename_strange_columns = False):
        """
        Tells the mind to learn to predict a column or columns from the data in 'from_data'

        Mandatory arguments:
        :param columns_to_predict: what column or columns you want to predict
        :param from_data: the data that you want to learn from, this can be either a file, a pandas data frame, or url to a file

        Optional arguments:
        :param test_from_data: If you would like to test this learning from a different data set

        Optional Time series arguments:
        :param order_by: this order by defines the time series, it can be a list. By default it sorts each sort by column in ascending manner, if you want to change this pass a touple ('column_name', 'boolean_for_ascending <default=true>')
        :param group_by: This argument tells the time series that it should learn by grouping rows by a given id
        :param window_size: The number of samples to learn from in the time series

        Optional data transformation arguments:
        :param ignore_columns: it simply removes the columns from the data sources
        :param rename_strange_columns: this tells mindsDB that if columns have special characters, it should try to rename them, this is a legacy argument, as now mindsdb supports any column name

        Optional sampling parameters:
        :param sample_margin_error (DEFAULT 0): Maximum expected difference between the true population parameter, such as the mean, and the sample estimate.
        :param sample_confidence_level (DEFAULT 0.98): number in the interval (0, 1) If we were to draw a large number of equal-size samples from the population, the true population parameter should lie within this percentage of the intervals (sample_parameter - e, sample_parameter + e) where e is the margin_error.

        Optional debug arguments:
        :param breakpoint: If you want the learn process to stop at a given 'PHASE' checkout libs/phases


        :return:
        """


        from_ds = getDS(from_data)
        test_from_ds = test_from_data if test_from_data is None else getDS(test_from_data)

        transaction_type = TRANSACTION_LEARN

        predict_columns_map = {}

        # lets turn into lists: predict, order_by and group by
        predict_columns = [columns_to_predict] if type(columns_to_predict) != type([]) else columns_to_predict
        group_by = group_by if type(group_by) == type([]) else [group_by] if group_by else []
        order_by = order_by if type(order_by) == type([]) else [order_by] if group_by else []

        if len(predict_columns) == 0:
            error = 'You need to specify a column to predict'
            self.log.error(error)
            raise ValueError(error)

        # lets turn order by into tuples if not already
        # each element ('column_name', 'boolean_for_ascending <default=true>')
        order_by = [(col_name, True) if type(col_name) != type(()) else col_name for col_name in order_by]

        is_time_series = True if len(order_by) > 0 else False

        if rename_strange_columns is False:
            for predict_col in predict_columns:
                predict_col_as_in_df = from_ds.getColNameAsInDF(predict_col)
                predict_columns_map[predict_col_as_in_df]=predict_col

            predict_columns = list(predict_columns_map.keys())
        else:
            self.log.warning('Note that after version 1.0, the default value for argument rename_strange_columns in MindsDB().learn, will be flipped from True to False, this means that if your data has columns with special characters, MindsDB will not try to rename them by default.')

        transaction_metadata = TransactionMetadata()
        transaction_metadata.model_name = self.mind_name
        transaction_metadata.model_predict_columns = predict_columns
        transaction_metadata.model_columns_map = {} if rename_strange_columns else from_ds._col_map
        transaction_metadata.model_group_by = group_by
        transaction_metadata.model_order_by = order_by
        transaction_metadata.model_is_time_series = is_time_series
        transaction_metadata.window_size = window_size
        transaction_metadata.type = transaction_type
        transaction_metadata.from_data = from_ds
        transaction_metadata.test_from_data = test_from_ds
        transaction_metadata.ignore_columns = ignore_columns
        transaction_metadata.sample_margin_of_error = sample_margin_of_error
        transaction_metadata.sample_confidence_level = sample_confidence_level

        Transaction(session=self, transaction_metadata=transaction_metadata, logger=self.log, breakpoint=breakpoint)


    def predict(self, when={}, when_data = None, breakpoint= PHASE_END):
        """

        :param predict:
        :param when:
        :return:
        """



        transaction_type = TRANSACTION_PREDICT

        from_ds = None if when_data is None else getDS(when_data)

        transaction_metadata = TransactionMetadata()
        transaction_metadata.model_name = self.mind_name

        # lets turn into lists: when
        when = when if type(when) in [type(None), type({})] else [when]


        # This will become irrelevant as if we have trained a model with a predict we just need to pass when or from_data
        # predict_columns = [predict] if type(predict) != type([]) else predict
        # transaction_metadata.model_predict_columns = predict_columns

        transaction_metadata.model_when_conditions = when
        transaction_metadata.type = transaction_type
        #transaction_metadata.storage_file = self.storage_file
        transaction_metadata.from_data = from_ds

        transaction = self.session.newTransaction(transaction_metadata, breakpoint)

        return transaction.output_data

