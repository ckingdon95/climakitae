########################################
#                                      #
# THRESHOLD TOOLS                      #
#                                      #
########################################

from multiprocessing.sharedctypes import Value
import numpy as np
import pandas as pd
import xarray as xr
from scipy import stats
import panel as pn

import lmoments3 as lm
from lmoments3 import distr as ldistr
from lmoments3 import stats as lstats

import matplotlib.pyplot as plt
from matplotlib import cm
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import geoviews as gv

import holoviews as hv
from holoviews import opts
import hvplot.pandas
import hvplot.xarray

from .visualize import get_geospatial_plot

#####################################################################


def get_ams(da, extremes_type="max"):
    """
    Returns a data array of annual maximums.
    """

    extremes_types = ["max"]
    if extremes_type not in extremes_types:
        raise ValueError(
            "invalid extremes type. expected one of the following: %s" % extremes_types
        )

    if extremes_type == "max":
        ams = da.resample(time="A").max(keep_attrs=True)
        ams.attrs["extreme value extraction method"] = "block maxima"
        ams.attrs["extremes type"] = "maxima"
        ams.attrs["block size"] = "1 year"
        ams.attrs["timeseries type"] = "annual max series"

    # if extremes_type == 'min':
    #     ams = da.resample(time='A').min(keep_attrs=True)
    #     ams.attrs['extreme value extraction method'] = 'block maxima'
    #     ams.attrs['extremes type'] = 'minima'
    #     ams.attrs['block size'] = '1 year'
    #     ams.attrs['timeseries type'] = 'annual min series'

    return ams


#####################################################################


def get_lmom_distr(distr):
    """
    Returns corresponding l-moments distribution function from selected distribution name.
    """

    distrs = ["gev", "gumbel", "weibull", "pearson3", "genpareto"]
    if distr not in distrs:
        raise ValueError(
            "invalid distr type. expected one of the following: %s" % distrs
        )

    if distr == "gev":
        lmom_distr = ldistr.gev

    elif distr == "gumbel":
        lmom_distr = ldistr.gum

    elif distr == "weibull":
        lmom_distr = ldistr.wei

    elif distr == "pearson3":
        lmom_distr = ldistr.pe3

    elif distr == "genpareto":
        lmom_distr = ldistr.gpa

    return lmom_distr


#####################################################################


def get_fitted_distr(ams, distr, lmom_distr):
    """
    Returns fitted l-moments distribution function from l-moments.
    """

    if distr == "gev":
        lmoments = lmom_distr.lmom_fit(ams)
        fitted_distr = stats.genextreme(**lmoments)

    elif distr == "gumbel":
        lmoments = lmom_distr.lmom_fit(ams)
        fitted_distr = stats.gumbel_r(**lmoments)

    elif distr == "weibull":
        lmoments = lmom_distr.lmom_fit(ams)
        fitted_distr = stats.weibull_min(**lmoments)

    elif distr == "pearson3":
        lmoments = lmom_distr.lmom_fit(ams)
        fitted_distr = stats.pearson3(**lmoments)

    elif distr == "genpareto":
        lmoments = lmom_distr.lmom_fit(ams)
        fitted_distr = stats.genpareto(**lmoments)

    return lmoments, fitted_distr


#####################################################################


def get_lmoments(ams, distr="gev", multiple_points=True):
    """
    Returns dataset of l-moments ratios from an inputed maximum series.
    """

    lmom_distr = get_lmom_distr(distr)
    ams_attributes = ams.attrs

    if multiple_points:
        ams = ams.stack(allpoints=["y", "x"]).squeeze().groupby("allpoints")

    lmoments = xr.apply_ufunc(
        lmom_distr.lmom_fit,
        ams,
        input_core_dims=[["time"]],
        exclude_dims=set(("time",)),
        output_core_dims=[[]],
    )

    lmoments = lmoments.rename("lmoments")
    new_ds = lmoments.to_dataset().to_array()

    if multiple_points:
        new_ds = new_ds.unstack("allpoints")

    new_ds.attrs = ams_attributes
    new_ds.attrs["distribution"] = "{}".format(str(distr))

    return new_ds


#####################################################################


def get_ks_stat(ams, distr="gev", multiple_points=True):
    """
    Returns a dataset of ks test d-statistics and p-values from an inputed maximum series.
    """

    lmom_distr = get_lmom_distr(distr)
    ams_attributes = ams.attrs

    if multiple_points:
        ams = ams.stack(allpoints=["y", "x"]).squeeze().groupby("allpoints")

    def ks_stat(ams):

        if distr == "gev":
            try:
                lmoments, fitted_distr = get_fitted_distr(ams, distr, lmom_distr)
                ks = stats.kstest(
                    ams,
                    "genextreme",
                    args=(lmoments["c"], lmoments["loc"], lmoments["scale"]),
                )
                d_statistic = ks[0]
                p_value = ks[1]
            except (ValueError, ZeroDivisionError):
                d_statistic = np.nan
                p_value = np.nan

        elif distr == "gumbel":
            try:
                lmoments, fitted_distr = get_fitted_distr(ams, distr, lmom_distr)
                ks = stats.kstest(
                    ams, "gumbel_r", args=(lmoments["loc"], lmoments["scale"])
                )
                d_statistic = ks[0]
                p_value = ks[1]
            except (ValueError, ZeroDivisionError):
                d_statistic = np.nan
                p_value = np.nan

        elif distr == "weibull":
            try:
                lmoments, fitted_distr = get_fitted_distr(ams, distr, lmom_distr)
                ks = stats.kstest(
                    ams,
                    "weibull_min",
                    args=(lmoments["c"], lmoments["loc"], lmoments["scale"]),
                )
                d_statistic = ks[0]
                p_value = ks[1]
            except (ValueError, ZeroDivisionError):
                d_statistic = np.nan
                p_value = np.nan

        elif distr == "pearson3":
            try:
                lmoments, fitted_distr = get_fitted_distr(ams, distr, lmom_distr)
                ks = stats.kstest(
                    ams,
                    "pearson3",
                    args=(lmoments["skew"], lmoments["loc"], lmoments["scale"]),
                )
                d_statistic = ks[0]
                p_value = ks[1]
            except (ValueError, ZeroDivisionError):
                d_statistic = np.nan
                p_value = np.nan

        elif distr == "genpareto":
            try:
                lmoments, fitted_distr = get_fitted_distr(ams, distr, lmom_distr)
                ks = stats.kstest(
                    ams,
                    "genpareto",
                    args=(lmoments["c"], lmoments["loc"], lmoments["scale"]),
                )
                d_statistic = ks[0]
                p_value = ks[1]
            except (ValueError, ZeroDivisionError):
                d_statistic = np.nan
                p_value = np.nan

        return d_statistic, p_value

    d_statistic, p_value = xr.apply_ufunc(
        ks_stat,
        ams,
        input_core_dims=[["time"]],
        exclude_dims=set(("time",)),
        output_core_dims=[[], []],
    )

    d_statistic = d_statistic.rename("d_statistic")
    new_ds = d_statistic.to_dataset()
    new_ds["p_value"] = p_value

    if multiple_points:
        new_ds = new_ds.unstack("allpoints")

    new_ds["d_statistic"].attrs["stat test"] = "KS test"
    new_ds["p_value"].attrs["stat test"] = "KS test"
    new_ds.attrs = ams_attributes
    new_ds.attrs["distribution"] = "{}".format(str(distr))

    return new_ds


#####################################################################


def calculate_return(fitted_distr, data_variable, arg_value):
    """
    Returns corresponding extreme value calculation for selected data variable.
    """

    if data_variable == "return_value":
        try:
            return_event = 1.0 - (1.0 / arg_value)
            return_value = fitted_distr.ppf(return_event)
            result = round(return_value, 5)
        except (ValueError, ZeroDivisionError, AttributeError):
            result = np.nan

    elif data_variable == "return_prob":
        try:
            result = 1 - (fitted_distr.cdf(arg_value))
        except (ValueError, ZeroDivisionError, AttributeError):
            result = np.nan

    elif data_variable == "return_period":
        try:
            return_prob = fitted_distr.cdf(arg_value)
            if return_prob == 1.0:
                result = np.nan
            else:
                return_period = -1.0 / (return_prob - 1.0)
                result = round(return_period, 3)
        except (ValueError, ZeroDivisionError, AttributeError):
            result = np.nan

    return result


#####################################################################


def bootstrap(ams, distr="gev", data_variable="return_value", arg_value=10):
    """
    Returns a bootstrap-calculated value for relevant parameters from a inputed maximum series.
    """

    data_variables = ["return_value", "return_prob", "return_period"]
    if data_variable not in data_variables:
        raise ValueError(
            "invalid data variable type. expected one of the following: %s"
            % data_variables
        )

    lmom_distr = get_lmom_distr(distr)

    sample_size = len(ams)
    new_ams = np.random.choice(ams, size=sample_size, replace=True)

    if distr == "gev":
        try:
            lmoments, fitted_distr = get_fitted_distr(new_ams, distr, lmom_distr)
            result = calculate_return(
                fitted_distr=fitted_distr,
                data_variable=data_variable,
                arg_value=arg_value,
            )
        except (ValueError, ZeroDivisionError):
            result = np.nan

    elif distr == "gumbel":
        try:
            lmoments, fitted_distr = get_fitted_distr(new_ams, distr, lmom_distr)
            result = calculate_return(
                fitted_distr=fitted_distr,
                data_variable=data_variable,
                arg_value=arg_value,
            )
        except (ValueError, ZeroDivisionError):
            result = np.nan

    elif distr == "weibull":
        try:
            lmoments, fitted_distr = get_fitted_distr(new_ams, distr, lmom_distr)
            result = calculate_return(
                fitted_distr=fitted_distr,
                data_variable=data_variable,
                arg_value=arg_value,
            )
        except (ValueError, ZeroDivisionError):
            result = np.nan

    elif distr == "pearson3":
        try:
            lmoments, fitted_distr = get_fitted_distr(new_ams, distr, lmom_distr)
            result = calculate_return(
                fitted_distr=fitted_distr,
                data_variable=data_variable,
                arg_value=arg_value,
            )
        except (ValueError, ZeroDivisionError):
            result = np.nan

    elif distr == "genpareto":
        try:
            lmoments, fitted_distr = get_fitted_distr(new_ams, distr, lmom_distr)
            result = calculate_return(
                fitted_distr=fitted_distr,
                data_variable=data_variable,
                arg_value=arg_value,
            )
        except (ValueError, ZeroDivisionError):
            result = np.nan

    return result


#####################################################################


def conf_int(
    ams,
    distr,
    data_variable,
    arg_value,
    bootstrap_runs,
    conf_int_lower_bound,
    conf_int_upper_bound,
):
    """
    Returns lower and upper limits of confidence interval given selected parameters.
    """

    bootstrap_values = []

    for _ in range(bootstrap_runs):
        result = bootstrap(ams, distr, data_variable, arg_value,)
        bootstrap_values.append(result)

    conf_int_array = np.percentile(
        bootstrap_values, [conf_int_lower_bound, conf_int_upper_bound]
    )

    conf_int_lower_limit = conf_int_array[0]
    conf_int_upper_limit = conf_int_array[1]

    return conf_int_lower_limit, conf_int_upper_limit


#####################################################################


def get_return_value(
    ams,
    return_period=10,
    distr="gev",
    bootstrap_runs=100,
    conf_int_lower_bound=2.5,
    conf_int_upper_bound=97.5,
    multiple_points=True,
):
    """
    Returns dataset with return values and confidence intervals from maximum series.
    """

    data_variable = "return_value"
    lmom_distr = get_lmom_distr(distr)
    ams_attributes = ams.attrs

    if multiple_points:
        ams = ams.stack(allpoints=["y", "x"]).squeeze().groupby("allpoints")

    def return_value(ams):

        if distr == "gev":
            try:
                lmoments, fitted_distr = get_fitted_distr(ams, distr, lmom_distr)
                return_value = calculate_return(
                    fitted_distr=fitted_distr,
                    data_variable=data_variable,
                    arg_value=return_period,
                )
            except (ValueError, ZeroDivisionError):
                return_value = np.nan
            conf_int_lower_limit, conf_int_upper_limit = conf_int(
                ams=ams,
                distr=distr,
                data_variable=data_variable,
                arg_value=return_period,
                bootstrap_runs=bootstrap_runs,
                conf_int_lower_bound=conf_int_lower_bound,
                conf_int_upper_bound=conf_int_upper_bound,
            )

        elif distr == "gumbel":
            try:
                lmoments, fitted_distr = get_fitted_distr(ams, distr, lmom_distr)
                return_value = calculate_return(
                    fitted_distr=fitted_distr,
                    data_variable=data_variable,
                    arg_value=return_period,
                )
            except (ValueError, ZeroDivisionError):
                return_value = np.nan
            conf_int_lower_limit, conf_int_upper_limit = conf_int(
                ams=ams,
                distr=distr,
                data_variable=data_variable,
                arg_value=return_period,
                bootstrap_runs=bootstrap_runs,
                conf_int_lower_bound=conf_int_lower_bound,
                conf_int_upper_bound=conf_int_upper_bound,
            )

        elif distr == "weibull":
            try:
                lmoments, fitted_distr = get_fitted_distr(ams, distr, lmom_distr)
                return_value = calculate_return(
                    fitted_distr=fitted_distr,
                    data_variable=data_variable,
                    arg_value=return_period,
                )
            except (ValueError, ZeroDivisionError):
                return_value = np.nan
            conf_int_lower_limit, conf_int_upper_limit = conf_int(
                ams=ams,
                distr=distr,
                data_variable=data_variable,
                arg_value=return_period,
                bootstrap_runs=bootstrap_runs,
                conf_int_lower_bound=conf_int_lower_bound,
                conf_int_upper_bound=conf_int_upper_bound,
            )

        elif distr == "pearson3":
            try:
                lmoments, fitted_distr = get_fitted_distr(ams, distr, lmom_distr)
                return_value = calculate_return(
                    fitted_distr=fitted_distr,
                    data_variable=data_variable,
                    arg_value=return_period,
                )
            except (ValueError, ZeroDivisionError):
                return_value = np.nan
            conf_int_lower_limit, conf_int_upper_limit = conf_int(
                ams=ams,
                distr=distr,
                data_variable=data_variable,
                arg_value=return_period,
                bootstrap_runs=bootstrap_runs,
                conf_int_lower_bound=conf_int_lower_bound,
                conf_int_upper_bound=conf_int_upper_bound,
            )

        elif distr == "genpareto":
            try:
                lmoments, fitted_distr = get_fitted_distr(ams, distr, lmom_distr)
                return_value = calculate_return(
                    fitted_distr=fitted_distr,
                    data_variable=data_variable,
                    arg_value=return_period,
                )
            except (ValueError, ZeroDivisionError):
                return_value = np.nan
            conf_int_lower_limit, conf_int_upper_limit = conf_int(
                ams=ams,
                distr=distr,
                data_variable=data_variable,
                arg_value=return_period,
                bootstrap_runs=bootstrap_runs,
                conf_int_lower_bound=conf_int_lower_bound,
                conf_int_upper_bound=conf_int_upper_bound,
            )

        return return_value, conf_int_lower_limit, conf_int_upper_limit

    return_value, conf_int_lower_limit, conf_int_upper_limit = xr.apply_ufunc(
        return_value,
        ams,
        input_core_dims=[["time"]],
        exclude_dims=set(("time",)),
        output_core_dims=[[], [], []],
    )

    return_value = return_value.rename("return_value")
    new_ds = return_value.to_dataset()
    new_ds["conf_int_lower_limit"] = conf_int_lower_limit
    new_ds["conf_int_upper_limit"] = conf_int_upper_limit

    if multiple_points:
        new_ds = new_ds.unstack("allpoints")

    new_ds["return_value"].attrs["return period"] = "1 in {} year event".format(
        str(return_period)
    )
    new_ds["conf_int_lower_limit"].attrs[
        "confidence interval lower bound"
    ] = "{}th percentile".format(str(conf_int_lower_bound))
    new_ds["conf_int_upper_limit"].attrs[
        "confidence interval upper bound"
    ] = "{}th percentile".format(str(conf_int_upper_bound))

    new_ds.attrs = ams_attributes
    new_ds.attrs["distribution"] = "{}".format(str(distr))

    return new_ds


#####################################################################


def get_return_prob(
    ams,
    threshold,
    distr="gev",
    bootstrap_runs=100,
    conf_int_lower_bound=2.5,
    conf_int_upper_bound=97.5,
    multiple_points=True,
):
    """
    Returns dataset with return probabilities and confidence intervals from maximum series.
    """

    data_variable = "return_prob"
    lmom_distr = get_lmom_distr(distr)
    ams_attributes = ams.attrs

    if multiple_points:
        ams = ams.stack(allpoints=["y", "x"]).squeeze().groupby("allpoints")

    def return_prob(ams):

        if distr == "gev":
            try:
                lmoments, fitted_distr = get_fitted_distr(ams, distr, lmom_distr)
                return_prob = calculate_return(
                    fitted_distr=fitted_distr,
                    data_variable=data_variable,
                    arg_value=threshold,
                )
            except (ValueError, ZeroDivisionError):
                return_prob = np.nan
            conf_int_lower_limit, conf_int_upper_limit = conf_int(
                ams=ams,
                distr=distr,
                data_variable=data_variable,
                arg_value=threshold,
                bootstrap_runs=bootstrap_runs,
                conf_int_lower_bound=conf_int_lower_bound,
                conf_int_upper_bound=conf_int_upper_bound,
            )

        elif distr == "gumbel":
            try:
                lmoments, fitted_distr = get_fitted_distr(ams, distr, lmom_distr)
                return_prob = calculate_return(
                    fitted_distr=fitted_distr,
                    data_variable=data_variable,
                    arg_value=threshold,
                )
            except (ValueError, ZeroDivisionError):
                return_prob = np.nan
            conf_int_lower_limit, conf_int_upper_limit = conf_int(
                ams=ams,
                distr=distr,
                data_variable=data_variable,
                arg_value=threshold,
                bootstrap_runs=bootstrap_runs,
                conf_int_lower_bound=conf_int_lower_bound,
                conf_int_upper_bound=conf_int_upper_bound,
            )

        elif distr == "weibull":
            try:
                lmoments, fitted_distr = get_fitted_distr(ams, distr, lmom_distr)
                return_prob = calculate_return(
                    fitted_distr=fitted_distr,
                    data_variable=data_variable,
                    arg_value=threshold,
                )
            except (ValueError, ZeroDivisionError):
                return_prob = np.nan
            conf_int_lower_limit, conf_int_upper_limit = conf_int(
                ams=ams,
                distr=distr,
                data_variable=data_variable,
                arg_value=threshold,
                bootstrap_runs=bootstrap_runs,
                conf_int_lower_bound=conf_int_lower_bound,
                conf_int_upper_bound=conf_int_upper_bound,
            )

        elif distr == "pearson3":
            try:
                lmoments, fitted_distr = get_fitted_distr(ams, distr, lmom_distr)
                return_prob = calculate_return(
                    fitted_distr=fitted_distr,
                    data_variable=data_variable,
                    arg_value=threshold,
                )
            except (ValueError, ZeroDivisionError):
                return_prob = np.nan
            conf_int_lower_limit, conf_int_upper_limit = conf_int(
                ams=ams,
                distr=distr,
                data_variable=data_variable,
                arg_value=threshold,
                bootstrap_runs=bootstrap_runs,
                conf_int_lower_bound=conf_int_lower_bound,
                conf_int_upper_bound=conf_int_upper_bound,
            )

        elif distr == "genpareto":
            try:
                lmoments, fitted_distr = get_fitted_distr(ams, distr, lmom_distr)
                return_prob = calculate_return(
                    fitted_distr=fitted_distr,
                    data_variable=data_variable,
                    arg_value=threshold,
                )
            except (ValueError, ZeroDivisionError):
                return_prob = np.nan
            conf_int_lower_limit, conf_int_upper_limit = conf_int(
                ams=ams,
                distr=distr,
                data_variable=data_variable,
                arg_value=threshold,
                bootstrap_runs=bootstrap_runs,
                conf_int_lower_bound=conf_int_lower_bound,
                conf_int_upper_bound=conf_int_upper_bound,
            )

        return return_prob, conf_int_lower_limit, conf_int_upper_limit

    return_prob, conf_int_lower_limit, conf_int_upper_limit = xr.apply_ufunc(
        return_prob,
        ams,
        input_core_dims=[["time"]],
        exclude_dims=set(("time",)),
        output_core_dims=[[], [], []],
    )

    return_prob = return_prob.rename("return_prob")
    new_ds = return_prob.to_dataset()
    new_ds["conf_int_lower_limit"] = conf_int_lower_limit
    new_ds["conf_int_upper_limit"] = conf_int_upper_limit

    if multiple_points:
        new_ds = new_ds.unstack("allpoints")

    new_ds["return_prob"].attrs["threshold"] = "exceedance of {} value event".format(
        str(threshold)
    )
    new_ds["conf_int_lower_limit"].attrs[
        "confidence interval lower bound"
    ] = "{}th percentile".format(str(conf_int_lower_bound))
    new_ds["conf_int_upper_limit"].attrs[
        "confidence interval upper bound"
    ] = "{}th percentile".format(str(conf_int_upper_bound))

    new_ds.attrs = ams_attributes
    new_ds.attrs["distribution"] = "{}".format(str(distr))

    return new_ds


#####################################################################


def get_return_period(
    ams,
    return_value,
    distr="gev",
    bootstrap_runs=100,
    conf_int_lower_bound=2.5,
    conf_int_upper_bound=97.5,
    multiple_points=True,
):
    """
    Returns dataset with return periods and confidence intervals from maximum series.
    """

    data_variable = "return_period"
    lmom_distr = get_lmom_distr(distr)
    ams_attributes = ams.attrs

    if multiple_points:
        ams = ams.stack(allpoints=["y", "x"]).squeeze().groupby("allpoints")

    def return_period(ams):

        if distr == "gev":
            try:
                lmoments, fitted_distr = get_fitted_distr(ams, distr, lmom_distr)
                return_period = calculate_return(
                    fitted_distr=fitted_distr,
                    data_variable=data_variable,
                    arg_value=return_value,
                )
            except (ValueError, ZeroDivisionError):
                return_period = np.nan
            conf_int_lower_limit, conf_int_upper_limit = conf_int(
                ams=ams,
                distr=distr,
                data_variable=data_variable,
                arg_value=return_value,
                bootstrap_runs=bootstrap_runs,
                conf_int_lower_bound=conf_int_lower_bound,
                conf_int_upper_bound=conf_int_upper_bound,
            )

        elif distr == "gumbel":
            try:
                lmoments, fitted_distr = get_fitted_distr(ams, distr, lmom_distr)
                return_period = calculate_return(
                    fitted_distr=fitted_distr,
                    data_variable=data_variable,
                    arg_value=return_value,
                )
            except (ValueError, ZeroDivisionError):
                return_period = np.nan
            conf_int_lower_limit, conf_int_upper_limit = conf_int(
                ams=ams,
                distr=distr,
                data_variable=data_variable,
                arg_value=return_value,
                bootstrap_runs=bootstrap_runs,
                conf_int_lower_bound=conf_int_lower_bound,
                conf_int_upper_bound=conf_int_upper_bound,
            )

        elif distr == "weibull":
            try:
                lmoments, fitted_distr = get_fitted_distr(ams, distr, lmom_distr)
                return_period = calculate_return(
                    fitted_distr=fitted_distr,
                    data_variable=data_variable,
                    arg_value=return_value,
                )
            except (ValueError, ZeroDivisionError):
                return_period = np.nan
            conf_int_lower_limit, conf_int_upper_limit = conf_int(
                ams=ams,
                distr=distr,
                data_variable=data_variable,
                arg_value=return_value,
                bootstrap_runs=bootstrap_runs,
                conf_int_lower_bound=conf_int_lower_bound,
                conf_int_upper_bound=conf_int_upper_bound,
            )

        elif distr == "pearson3":
            try:
                lmoments, fitted_distr = get_fitted_distr(ams, distr, lmom_distr)
                return_period = calculate_return(
                    fitted_distr=fitted_distr,
                    data_variable=data_variable,
                    arg_value=return_value,
                )
            except (ValueError, ZeroDivisionError):
                return_period = np.nan
            conf_int_lower_limit, conf_int_upper_limit = conf_int(
                ams=ams,
                distr=distr,
                data_variable=data_variable,
                arg_value=return_value,
                bootstrap_runs=bootstrap_runs,
                conf_int_lower_bound=conf_int_lower_bound,
                conf_int_upper_bound=conf_int_upper_bound,
            )

        elif distr == "genpareto":
            try:
                lmoments, fitted_distr = get_fitted_distr(ams, distr, lmom_distr)
                return_period = calculate_return(
                    fitted_distr=fitted_distr,
                    data_variable=data_variable,
                    arg_value=return_value,
                )
            except (ValueError, ZeroDivisionError):
                return_period = np.nan
            conf_int_lower_limit, conf_int_upper_limit = conf_int(
                ams=ams,
                distr=distr,
                data_variable=data_variable,
                arg_value=return_value,
                bootstrap_runs=bootstrap_runs,
                conf_int_lower_bound=conf_int_lower_bound,
                conf_int_upper_bound=conf_int_upper_bound,
            )

        return return_period, conf_int_lower_limit, conf_int_upper_limit

    return_period, conf_int_lower_limit, conf_int_upper_limit = xr.apply_ufunc(
        return_period,
        ams,
        input_core_dims=[["time"]],
        exclude_dims=set(("time",)),
        output_core_dims=[[], [], []],
    )

    return_period = return_period.rename("return_period")
    new_ds = return_period.to_dataset()
    new_ds["conf_int_lower_limit"] = conf_int_lower_limit
    new_ds["conf_int_upper_limit"] = conf_int_upper_limit

    if multiple_points:
        new_ds = new_ds.unstack("allpoints")

    new_ds["return_period"].attrs[
        "return value"
    ] = "occurrence of a {} value event".format(str(return_value))
    new_ds["conf_int_lower_limit"].attrs[
        "confidence interval lower bound"
    ] = "{}th percentile".format(str(conf_int_lower_bound))
    new_ds["conf_int_upper_limit"].attrs[
        "confidence interval upper bound"
    ] = "{}th percentile".format(str(conf_int_upper_bound))

    new_ds.attrs = ams_attributes
    new_ds.attrs["distribution"] = "{}".format(str(distr))

    return new_ds

def _parse_event_string(event_string):
    """
    Return a tuple with the 
    Error if not the correct format.
    
    Examples:
    "3days" --> (3, "day")
    "3day" --> (3, "day")
    "4months" --> (4, "month")
    "1year" --> (1, "year")

    """
    # Error if doesn't start with an integer

    # Split on numeric

    # Error if string not "day" "month" "year"
    #   TBD: offer hourly groupings?

    # Return tuple


def get_exceedance_events(
    da,
    threshold_value,
    threshold_direction = "above", 
    groupby = None
):
    """
    Returns a Boolean xarray that specifies whether each entry of da is a qualifying event.
    """
    # group_num, group_type = _parse_event_string(groupby)

    # Count occurances
    if threshold_direction == "above":
        events_da = (da > threshold_value)
    elif threshold_direction == "below":
        events_da = (da < threshold_value)
    else:
        raise ValueError(f"Unknown value for `threshold_direction` parameter: {threshold_direction}. Available options are 'above' or 'below'.")

    # Groupby 
    if groupby is not None:
        if groupby == "1day":
            day_totals = events_da.groupby("time.date").sum()
            events_da = day_totals > 0
            events_da["date"] = pd.to_datetime(events_da.date)
            events_da = events_da.rename({"date":"time"})
        else:
            raise ValueError("Duration options other than '1day' not yet implmented.")

    return events_da


def get_exceedance_count(
    da,
    threshold_value,
    period_length = "1year",
    threshold_direction = "above", 
    duration = None,
    groupby = None,
    smoothing = None
):
    """
    Calculate the number of occurances of exceeding the specified threshold_value
    within each period length.

    Returns an xarray with the same coordinates as the input data except for the time dimension.

    Arguments:
    da -- an xarray.DataArray of some climate variable. Can have mutliple scenarios, simulations,
        or x and y coordinates. 
    threshold_value -- value against which to test exceedance
    
    Optional Keyword Arguments:
    period_length -- amount of time across which to sum the number of occurances, default is 1 year. 
        Options: "1year", "1month", f"{x}year", f"{x}month" where x is an integer
    threshold_direction -- string either "above" or "below", default is above.
    duration -- length of exceedance in order to qualify as an event
    groupby -- see examples for explanation. Typical grouping could be "1day"
    smoothing -- option to average the result across 
    """

    #--------- Type check arguments -------------------------------------------

    # if da.frequencey != "hourly": raise ValueError("Must use hourly data for calls to `get_exceedance_count`")

    if duration is not None: raise ValueError("Duration option not yet implemented.")
    if smoothing is not None: raise ValueError("Smoothing option not yet implemented.")

    # period_num, period_type = _parse_event_string(period_length)
    # duration_num, duration_type = _parse_event_string(duration)

    # Need to check compatibility of periods, durations, and groupbys

    #--------- Calculate occurances -------------------------------------------

    events_da = get_exceedance_events(da, threshold_value, threshold_direction, groupby)

    #--------- Group by time period and count ---------------------------------
    
    if period_length == "1year":
        exceedance_count = events_da.groupby("time.year").sum()
    else:
        raise ValueError("Other period_length options not yet implemented. Please use '1year'.")

    return exceedance_count


def plot_exceedance_count(exceedance_count):
    """
    Plots each simulation as a different color line.
    Drop down option to select different scenario.
    Currently can only plot for one location, so is expecting input to already be subsetted or an area average.
    """
    # Need to add custom informative axis labels and title

    # Need to generalize x period length 
    
    plot_obj = exceedance_count.hvplot.line(
        x="year", widget_location="bottom", by="simulation", groupby=["scenario"]
    )
    return pn.Column(plot_obj)