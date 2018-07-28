__author__="Alexandr Savinov"

import json

from lambdo.utils import *
from lambdo.resolve import *
from lambdo.transform import *

import logging
log = logging.getLogger('WORKFLOW')


class Workflow:
    """
    The class represents a workflow.
    """

    workflowNo = 0

    def __init__(self, workflow_json: dict):

        self.workflow_json = workflow_json

        self.id = self.workflow_json.get('id', None)
        if self.id is None:
            self.id = "___workflow___" + str(self.workflowNo)
            self.workflow_json['id'] = self.id
            self.workflowNo += 1

        #
        # Prepare execution environment
        #
        imports = self.workflow_json.get('imports', [])
        self.modules = import_modules(imports)

        #
        # Create table objects
        #
        self.tables = self.create_tables()

    def create_tables(self):
        """Create a list of Table objects from json."""
        tables_json = self.workflow_json.get("tables", [])
        tables = [Table(self,x) for x in tables_json]
        return tables

    def get_tables(self, table_names):
        """Find tables with the specified names"""
        if not table_names: return None
        tables = filter(lambda x: x.id in table_names, self.tables)
        return list(tables)

    def get_table_number(self, table_name):
        """Find table number in the list"""
        return next(i for i, x in enumerate(self.tables) if x.id == table_name)

    def execute(self):
        """
        Execute the whole workflow.
        This means executing all tables according to their dependencies.
        """
        log.info("Start executing workflow '{0}'.".format(self.id))

        # Execute all tables. Later we will take into account their dependencies.
        for i, tab in enumerate(self.tables):
            tab.execute()

        log.info("Finish executing workflow '{0}'.".format(self.id))


class Table:
    """
    The class represents one table.
    """

    tableNo = 0

    def __init__(self, workflow: Workflow, table_json: dict):

        self.workflow = workflow
        self.table_json = table_json
        self.data = None

        self.id = self.table_json.get('id', None)
        if self.id is None:
            self.id = "___table___" + str(self.tableNo)
            self.table_json['id'] = self.id
            self.tableNo += 1

        # Create column objects
        columns_json = self.table_json.get("columns", [])
        self.columns = self.create_columns()

    def create_columns(self):
        """Create a list of Column objects from json."""
        columns_json = self.table_json.get("columns", [])
        columns = [Column(self,x) for x in columns_json]
        return columns

    def populate(self):
        """
        Populate this table with records.
        """
        #
        # Stage 1. Resolve the function
        #
        func_name = self.table_json.get('function')
        func = resolve_full_name(func_name)

        #
        # Stage 2. Prepare input data
        #
        inputs = self.table_json.get('inputs')
        tables = self.workflow.get_tables(inputs)
        if not tables: tables = []

        #
        # Stage 3. Prepare argument object to pass to the function as the second argument
        #
        model = self.table_json.get('model', {})

        #
        # Stage 6. Apply function
        #
        out = None
        if not func:
            this_table_no = self.workflow.get_table_number(self.id)
            if this_table_no and this_table_no > 0:
                input_table = self.workflow.tables[this_table_no-1]
                out = pd.DataFrame(input_table.data)
        elif len(tables) == 0:
            out = func(**model)
        elif len(tables) == 1:
            out = func(tables[0].data, **model)
        else:
            out = func(tables, **model)

        return out

    def execute(self):
        """
        Execute the whole table.
        This means populate it, execute all columns and then post-process.
        """
        log.info("===> Start populating table '{0}'".format(self.id))

        # Add records (populate)
        new_data = self.populate()
        if new_data is not None:
            self.data = new_data

        # Add derived columns (evaluate)
        for i, col in enumerate(self.columns):
            col.evaluate()

        #
        # Table row filter
        #

        #
        # Table column filter
        #

        log.info("<=== Finish populating table '{0}'".format(self.id))

class Column:
    """
    The class represents one column definition.
    """

    columnNo = 0

    def __init__(self, table: Table, column_json: dict):

        self.table = table
        self.column_json = column_json

        self.id = self.column_json.get('id', None)
        if self.id is None:
            self.id = "___column___" + str(self.columnNo)
            self.column_json['id'] = self.id
            self.columnNo += 1

    def get_definitions(self):
        """
        Produce all concrete definitions by imposing extensions onto the base definition.
        :return: List of concrete definitions. In the case of no extensions, only the base definition is returned.
        """
        base = self.column_json.copy()
        exts = self.column_json.get('extensions')

        if not exts: return [base]  # No extensions

        result = []
        for ext in exts:
            e = {**base, **ext}
            e = dict(e)  # Make copy
            del e['extensions']  # Remove extensions
            result.append(e)

        return result

    def evaluate(self):
        """
        Evaluate this column.
        """
        log.info("  ===> Start evaluating column '{0}'".format(self.id))

        #
        # Stage 1: Ensure that "data" field is ready for applying column operations
        #

        #
        # Stage 2: Generate a list of concrete definitions by imposing extensions on the base definition
        # "extensions" field determine family or not.
        #
        concrete_definitions = self.get_definitions()
        num_extensions = len(concrete_definitions)

        for i, definition in enumerate(concrete_definitions):

            #
            # Stage 3. Resolve the function
            #
            func_name = definition.get('function')
            func = resolve_full_name(func_name)
            if not func:
                log.warning("Cannot resolve user-defined function '{0}'. Skip column definition.".format(func_name))
                break

            #
            # Stage 4. Prepare input data argument to pass to the function (as the first argument)
            #
            X = self.table.data
            inputs = definition.get('inputs')
            if inputs is None:
                inputs = []
            inputs = get_columns(inputs, X)
            if inputs is None:
                log.warning("Error reading column list. Skip column definition.")
                break

            inX = None
            if inputs:
                all_inputs_available = True
                for col in inputs:
                    if col not in X.columns:
                        all_inputs_available = False
                        log.warning("Input column '{0}' is not available. Skip column definition.".format(col))
                        break
                if not all_inputs_available: break
                inX = X[inputs]  # Select only specified columns
            else:
                inX = X  # All columns

            #
            # Stage 5. Prepare model object to pass to the function (as the second argument)
            # It can be necessary to instantiate the argument object by using the specified class
            # It can be necessary to generate (train) a model (we need some specific logic to determine such a need)
            #
            model = definition.get('model')
            train = definition.get('train')
            if not model and train is not None:

                # 1. Resolve train function
                train_func_name = train.get('function')
                train_func = resolve_full_name(train_func_name)
                if not train_func:
                    log.warning("Cannot resolve user-defined training function '{0}'. Skip training.".format(train_func_name))
                    break

                # 2. TODO: Determine input data

                # 3. Determine labels
                # - no labels at all (no argument is expected) - unsupervised learning
                # - explicitly specified outputs
                # - use output column specified in the transformation (but it has to be already available, e.g., loaded from source data, while the transformation will overwrite it)
                labels = train.get('outputs')
                if not labels:
                    labels = definition.get('outputs')  # Same columns as used by the transformation

                if labels:
                    labels = get_columns(labels, X)
                    if labels is None:
                        log.warning("Error reading column list. Skip column definition.")
                        break
                    y = X[labels]  # Select only specified columns
                else:
                    y = None  # Do not pass any labels at all

                # 4. Retrieve hyper-model
                train_model = train.get('model', {})

                # 5. Make call and return model
                if y is None:
                    model = train_func(inX, **train_model)
                else:
                    model = train_func(inX, y, **train_model)

            elif not model and not train:
                model = {}


            #
            # Stage 6. Apply function.
            # Depending on the "scope" the system will organize a loop over records, windows or make single call
            # It also depends on the call options (how and what to pass in data and model arguments, flatten json, ndarry or Series etc.)
            #
            scope = definition.get('scope')
            options = definition.get('options')
            out = transform(func, inX, model, scope, options)

            #
            # Stage 7. Post-process the result by renaming the output columns accordingly (some convention is needed to know what output to expect)
            #
            outputs = definition.get('outputs', [])
            if isinstance(outputs, str):  # If a single name is provided (not a list), then we wrap into a list
                outputs = [outputs]
            if not outputs:
                id = definition.get('id')
                # TODO: We could use a smarter logic here by finding a parameter of the extension which really changes (is overwritten): inputs, function, outputs, scope, model etc.
                if num_extensions > 1:
                    id = id + '_' + str(i)
                outputs.append(id)

            res = pd.DataFrame(X)  # Copy all input columns to the result

            out = pd.DataFrame(out)  # Result can be ndarray
            for i, c in enumerate(out.columns):
                if outputs and i < len(outputs):  # Explicitly specified output column name
                    n = outputs[i]
                else:  # Same name - overwrite input column
                    n = inputs[i]
                res[n] = out[c]

        #
        # Stage 8. Post-process the whole family
        #

        log.info("  <=== Finish evaluating column '{0}'".format(self.id))


if __name__ == "__main__":

    from sklearn import datasets, linear_model

    data = {'A': [1, 2, 3, 4], 'B': [1, 3, 3, 1]}
    df = pd.DataFrame(data)
    # X numpy array or sparse matrix of shape [n_samples,n_features]
    # y numpy array of shape [n_samples, n_targets]
    X = df[['A']].values
    y = df[['B']].values

    m = regression_fit(df[['A']], df[['B']])
    B_predict = regression_predict(df[['A']], m)



    model = linear_model.LinearRegression()

    # sklearn.linear_model.base
    # LinearRegression.fit
    model.fit(X, y)
    # ValueError: Expected 2D array, got 1D array instead: array=[1 2 3]
    # Reshape your data either using array.reshape(-1, 1) if your data has a single feature or array.reshape(1, -1) if it contains a single sample.


    y_pred = model.predict(X)

    pass
